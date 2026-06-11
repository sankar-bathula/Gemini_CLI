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

from app.doji_strategy import DojiSRStrategy
from app.data_collector import DataCollector

class TradingBot:
    def __init__(self, trading_symbol="Nifty 50", symbol_token="99926000"):
        self.trading_symbol = trading_symbol
        self.symbol_token = symbol_token
        
        self.client = AngelOneClient()
        self.db = DatabaseManager()
        self.collector = DataCollector(self.client)
        
        # Buffer for 5m timeframe (used by Doji strategy)
        self.buffer_5m = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Current candle placeholders
        self.current_5m = None
        
        self.strategy = DojiSRStrategy(rr_ratio=2.0)
        self.risk_manager = RiskManager()
        self.executor = None
        self.ws = None

    def handle_tick(self, msg):
        """
        Callback for WebSocket tick data.
        Updates data buffer and checks for strategy signals.
        """
        try:
            ltp = float(msg.get('last_traded_price', 0)) / 100
            if ltp == 0: return

            now = datetime.now()
            # Target 5m candles for the Doji strategy
            ts_5m = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)

            if self.current_5m is None or ts_5m > self.current_5m['timestamp']:
                if self.current_5m:
                    self._add_to_buffer(self.current_5m)
                self.current_5m = {
                    'timestamp': ts_5m, 'open': ltp, 'high': ltp, 'low': ltp, 'close': ltp, 'volume': 0
                }
            else:
                self.current_5m['high'] = max(self.current_5m['high'], ltp)
                self.current_5m['low'] = min(self.current_5m['low'], ltp)
                self.current_5m['close'] = ltp

        except Exception as e:
            logger.error(f"Error handling tick: {str(e)}")

    def _add_to_buffer(self, candle):
        # Save to DB
        if self.db and self.db.connection_pool:
            self.db.save_candle(self.trading_symbol, '5m', candle['timestamp'], 
                               candle['open'], candle['high'], candle['low'], candle['close'], candle['volume'])
        
        df_new = pd.DataFrame([candle])
        self.buffer_5m = pd.concat([self.buffer_5m, df_new], ignore_index=True)
        
        # Run Strategy
        if len(self.buffer_5m) >= 50:
            self.strategy.update_data(self.buffer_5m)
            signal, sl, tp = self.strategy.generate_signal()
            if signal != "HOLD":
                self.execute_trade(signal, sl, tp)
        
        if len(self.buffer_5m) > 500: self.buffer_5m = self.buffer_5m.iloc[1:]

    def execute_trade(self, side, strategy_sl, strategy_tp):
        """
        Executes trade by selecting the right weekly option premium.
        """
        try:
            # 1. Select Option Instrument (Premium around 250)
            option_type = "CE" if side == "BUY" else "PE"
            option_instr = self.collector.find_strike_by_premium(option_type, target_premium=250)
            
            if not option_instr:
                logger.error("Could not find a suitable option premium.")
                return

            premium_price = option_instr['ltp']
            logger.info(f"Selected {option_instr['symbol']} at premium {premium_price}")

            # 2. Risk Management
            # We use the strategy's SL/TP levels relative to the index
            # For simplicity in options, we calculate position size based on the premium
            balance = 100000 
            # Define a fixed risk per trade for options (e.g. 5000 rupees)
            risk_amount = 5000 
            quantity = (risk_amount // premium_price // 50) * 50 # Nifty lot size is 50
            
            if quantity > 0:
                logger.info(f"Executing trade: {side} {option_instr['symbol']} Qty: {quantity}")
                order_id = self.executor.place_market_order(option_instr['symbol'], option_instr['token'], "BUY", quantity, exchange="NFO")
                
                if order_id:
                    # Place a simple SL order on the premium (e.g. 20% SL)
                    sl_premium = round(premium_price * 0.8, 1)
                    self.executor.place_sl_order(option_instr['symbol'], option_instr['token'], "SELL", quantity, sl_premium, exchange="NFO")
            else:
                logger.warning("Calculated quantity is 0. Skipping trade.")
        except Exception as e:
            logger.error(f"Trade execution failed: {str(e)}")

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
    bot = TradingBot(trading_symbol="SBIN-EQ", symbol_token="3045")
    bot.start()
