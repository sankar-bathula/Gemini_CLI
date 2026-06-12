import time
import pandas as pd
from logzero import logger
from app.angel_api import AngelOneClient
from app.strategy import TradingStrategy
from app.risk import RiskManager
from app.execution import OrderExecutor
from app.websocket import AngelOneWebSocket
from app.database import DatabaseManager
from datetime import datetime
from fastapi import FastAPI
import uvicorn
import threading
from app.routes.dashboard import router as dashboard_router, set_bot_instance

from app.master_strategy import NiftySMCStrategy
from app.pattern_strategy import PatternStrategy
from app.data_collector import DataCollector
from app.notifier import WhatsAppNotifier

class TradingBot:
    def __init__(self, trading_symbol="Nifty 50", symbol_token="99926000", strategy_type="PATTERN"):
        self.trading_symbol = trading_symbol
        self.symbol_token = symbol_token
        self.strategy_type = strategy_type
        
        self.client = AngelOneClient()
        self.db = DatabaseManager()
        self.collector = DataCollector(self.client)
        self.notifier = WhatsAppNotifier()
        
        # Buffers for multi-timeframe analysis
        self.buffer_1h = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        self.buffer_15m = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        self.buffer_5m = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        self.current_1h = None
        self.current_15m = None
        self.current_5m = None
        
        if self.strategy_type == "SMC":
            self.strategy = NiftySMCStrategy(rr_ratio=3.0)
        else:
            self.strategy = PatternStrategy(rr_ratio=3.0)

        self.risk_manager = RiskManager(risk_per_trade=0.01) # 1% Risk
        self.active_trade = None
        self.executor = None
        self.ws = None
        
        # Option Metrics Cache
        self.last_metrics_update = 0
        self.selected_ce = None
        self.selected_pe = None

    def start_dashboard(self):
        """
        Starts the FastAPI dashboard server.
        """
        app = FastAPI(title="Trading Bot Dashboard")
        set_bot_instance(self)
        app.include_router(dashboard_router)
        
        def run():
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")
        
        server_thread = threading.Thread(target=run, daemon=True)
        server_thread.start()
        logger.info("Dashboard available at http://localhost:8000")

    def handle_tick(self, msg):
        try:
            ltp = float(msg.get('last_traded_price', 0)) / 100
            if ltp == 0: return

            # 1. Update Option Metrics every 5 minutes
            now_ts = time.time()
            if now_ts - self.last_metrics_update > 300: # 300 seconds = 5 mins
                self._update_option_metrics()
                self.last_metrics_update = now_ts

            # 2. Manage Trailing SL for Active Trade
            if self.active_trade:
                new_sl = self.risk_manager.trail_stop_loss(
                    ltp, self.active_trade['entry_price'], self.active_trade['sl'], 
                    self.active_trade['side']
                )
                if new_sl != self.active_trade['sl']:
                    logger.info(f"Trailing SL moved to {new_sl}")
                    self.active_trade['sl'] = new_sl
                    self.notifier.send_message(f"🔒 *Trailing SL Updated*\nNew SL: ₹{new_sl:.1f}")
                    # Update SL order in NFO if needed

            now = datetime.now()
            # 3. Aggregate buffers
            self._update_candles(ltp, now)

        except Exception as e:
            logger.error(f"Error handling tick: {str(e)}")

    def _update_option_metrics(self):
        """
        Fetches live option chain data and updates strategy filters.
        """
        logger.info("Updating Option Chain metrics (OI, PCR)...")
        df_chain = self.collector.get_option_chain_data()
        if df_chain is not None and not df_chain.empty:
            pcr = self.collector.calculate_pcr(df_chain)
            support, resistance = self.collector.identify_oi_levels(df_chain)
            self.strategy.update_option_metrics(df_chain, pcr, support, resistance)
            logger.info(f"Metrics updated: PCR={pcr}, OI Support={support}, OI Res={resistance}")

    def _update_candles(self, ltp, now):
        # Logic to aggregate 1h, 15m, 5m from ticks
        for tf, window_min in [('1h', 60), ('15m', 15), ('5m', 5)]:
            ts = now.replace(minute=(now.minute // window_min) * window_min, second=0, microsecond=0)
            attr = f"current_{tf}"
            curr = getattr(self, attr)
            
            if curr is None or ts > curr['timestamp']:
                if curr:
                    self._add_to_buffer(tf, curr)
                setattr(self, attr, {'timestamp': ts, 'open': ltp, 'high': ltp, 'low': ltp, 'close': ltp, 'volume': 0})
            else:
                curr['high'] = max(curr['high'], ltp)
                curr['low'] = min(curr['low'], ltp)
                curr['close'] = ltp

    def _add_to_buffer(self, timeframe, candle):
        df_new = pd.DataFrame([candle])
        buffer_attr = f"buffer_{timeframe}"
        buf = getattr(self, buffer_attr)
        setattr(self, buffer_attr, pd.concat([buf, df_new], ignore_index=True))
        
        # Strategy Flow
        if self.strategy_type == "SMC":
            if timeframe == '1h':
                self.strategy.update_bias(getattr(self, buffer_attr))
            elif timeframe == '15m':
                self.strategy.update_zones(getattr(self, buffer_attr))
            elif timeframe == '5m':
                if len(self.buffer_15m) >= 20:
                    signal, sl, tp = self.strategy.generate_signal(self.buffer_15m)
                    if signal != "HOLD":
                        self.execute_trade(signal, sl, tp)
        else:
            # PATTERN Strategy Logic
            if timeframe == '5m':
                if not self.selected_ce or not self.selected_pe:
                    self._update_selected_options()
                
                if self.selected_ce and self.selected_pe:
                    df_idx = self.buffer_5m.tail(20)
                    
                    # For simplicity, we check CE for patterns
                    # In production, we'd fetch both or use a bias
                    df_ce = self.collector.get_historical_candles("NFO", self.selected_ce['symbol'], self.selected_ce['token'], "FIVE_MINUTE", 
                                                                  (datetime.now() - timedelta(minutes=100)).strftime("%Y-%m-%d %H:%M"), 
                                                                  datetime.now().strftime("%Y-%m-%d %H:%M"))
                    
                    if df_ce is not None:
                        # Clean and format df_ce
                        df_ce['timestamp'] = pd.to_datetime(df_ce['timestamp'])
                        df_ce.set_index('timestamp', inplace=True)
                        for col in ['open', 'high', 'low', 'close']: df_ce[col] = pd.to_numeric(df_ce[col])
                        
                        signal, sl, tp = self.strategy.generate_signal(df_idx, df_ce)
                        if signal != "HOLD":
                            self.execute_trade(signal, sl, tp)

    def _update_selected_options(self):
        logger.info("Updating selected options for Pattern strategy...")
        self.selected_ce = self.collector.find_strike_by_premium("CE", 250)
        self.selected_pe = self.collector.find_strike_by_premium("PE", 250)


    def execute_trade(self, side, strategy_sl, strategy_tp):
        if self.active_trade: return
        
        try:
            # 1. Select Option
            option_type = "CE" if side == "BUY" else "PE"
            option_instr = self.collector.find_strike_by_premium(option_type, target_premium=250)
            if not option_instr: return

            # 2. Risk Management (1% Capital)
            balance = 100000 
            qty = self.risk_manager.calculate_position_size(balance, option_instr['ltp'], strategy_sl) # Simplified for Option price
            qty = (qty // 50) * 50 # Nifty lot

            if qty > 0:
                logger.info(f"Entering {side} on {option_instr['symbol']} with 1% Risk.")
                # Execute Market and SL orders...
                self.active_trade = {'side': side, 'entry_price': option_instr['ltp'], 'sl': strategy_sl, 'tp': strategy_tp, 'qty': qty}
                self.notifier.send_message(f"🚀 *TRADE EXECUTED*\nSide: {side}\nInstrument: {option_instr['symbol']}\nEntry: ₹{option_instr['ltp']}\nQty: {qty}\nSL: ₹{strategy_sl}\nTP: ₹{strategy_tp}")
        except Exception as e:
            logger.error(f"Execution failed: {e}")

    def start(self):
        self.db.connect()
        self.start_dashboard() 
        if self.client.login():
            self.executor = OrderExecutor(self.client)
            
            # Setup WebSocket
            session = self.client.session_data['data']
            feed_token = self.client.smart_api.getfeedToken()
            
            self.ws = AngelOneWebSocket(
                session['jwtToken'], 
                self.client.api_key, 
                self.client.client_code, 
                feed_token
            )
            self.ws.on_tick_callback = self.handle_tick
            self.ws.connect()
            self.ws.subscribe([self.symbol_token])
            
            logger.info(f"Bot started for {self.trading_symbol}. Waiting for ticks...")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")

if __name__ == "__main__":
    bot = TradingBot()
    bot.start()
