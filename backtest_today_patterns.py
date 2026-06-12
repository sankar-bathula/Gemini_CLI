import pandas as pd
import numpy as np
from app.angel_api import AngelOneClient
from app.data_collector import DataCollector
from app.pattern_strategy import PatternStrategy
from app.risk import RiskManager
from logzero import logger
from datetime import datetime, timedelta

class PatternBacktester:
    def __init__(self, initial_balance=100000):
        self.balance = initial_balance
        self.trades = []
        self.strategy = PatternStrategy(rr_ratio=3.0)
        self.risk_manager = RiskManager(risk_per_trade=0.01)

    def run(self, df_idx, df_ce, df_pe):
        logger.info(f"Starting Today's Candlestick Pattern & Premium Backtest...")
        
        active_trade = None
        
        # Use 5m index as the master timeline
        for i in range(10, len(df_idx)):
            current_time = df_idx.index[i]
            
            # 1. Manage Active Trade
            if active_trade:
                opt_df = df_ce if active_trade['option_type'] == 'CE' else df_pe
                if current_time in opt_df.index:
                    opt_row = opt_df.loc[current_time]
                    opt_price = opt_row['close']
                    
                    if active_trade['side'] == 'BUY' and opt_row['low'] <= active_trade['sl']:
                        self._close_trade(active_trade, active_trade['sl'], current_time, "STOP_LOSS")
                        active_trade = None
                    elif active_trade['side'] == 'BUY' and opt_row['high'] >= active_trade['tp']:
                        self._close_trade(active_trade, active_trade['tp'], current_time, "TAKE_PROFIT")
                        active_trade = None
                continue

            # 2. Strategy Logic
            hist_idx = df_idx.iloc[:i+1]
            
            # We check both CE and PE for patterns
            # Note: For simplicity, we just check if Index is Bullish -> look at CE, Bearish -> look at PE
            
            # We need to pass the corresponding option data to the strategy
            # Since we don't know the bias yet, we can check both or use a simple trend filter
            
            # Simple check: if Index has a pattern, check the premium
            # For CE
            if current_time in df_ce.index:
                hist_ce = df_ce[df_ce.index <= current_time]
                signal, sl, tp = self.strategy.generate_signal(hist_idx, hist_ce)
                if signal == "BUY":
                    self._open_trade(signal, "CE", df_ce.loc[current_time]['close'], current_time, sl, tp)
                    active_trade = self.trades[-1]
                    continue

            # For PE
            if current_time in df_pe.index:
                hist_pe = df_pe[df_pe.index <= current_time]
                signal, sl, tp = self.strategy.generate_signal(hist_idx, hist_pe)
                if signal == "SELL":
                    self._open_trade(signal, "PE", df_pe.loc[current_time]['close'], current_time, sl, tp)
                    active_trade = self.trades[-1]
                    continue

        self._print_results()

    def _open_trade(self, side, opt_type, price, time, sl, tp):
        qty = self.risk_manager.calculate_position_size(self.balance, price, sl)
        qty = (qty // 50) * 50
        if qty > 0:
            self.trades.append({
                'side': side,
                'option_type': opt_type,
                'entry_price': price,
                'entry_time': time,
                'sl': sl,
                'tp': tp,
                'qty': qty,
                'status': 'OPEN'
            })
            logger.info(f"OPEN: {side} {opt_type} at {price}")

    def _close_trade(self, trade, exit_price, exit_time, reason):
        pnl = (exit_price - trade['entry_price']) * trade['qty']
        self.balance += pnl
        trade.update({
            'exit_price': exit_price,
            'exit_time': exit_time,
            'pnl': pnl,
            'reason': reason,
            'status': 'CLOSED'
        })
        logger.info(f"CLOSE: {trade['option_type']} at {exit_price} ({reason}) | PnL: {pnl:.0f}")

    def _print_results(self):
        print("\n" + "="*45)
        print(" PATTERN & PREMIUM BACKTEST RESULTS ")
        print("="*45)
        if not self.trades:
            print("No trades triggered today based on patterns.")
        else:
            df_t = pd.DataFrame(self.trades)
            closed_trades = df_t[df_t['status'] == 'CLOSED']
            if closed_trades.empty:
                print("No trades closed today.")
            else:
                for _, t in closed_trades.iterrows():
                    print(f"{t['entry_time'].strftime('%H:%M')} | {t['option_type']} | Entry: {t['entry_price']:.1f} | Exit: {t['exit_price']:.1f} | PnL: {t['pnl']:.0f}")
                
                print("-"*45)
                print(f"Total Trades: {len(closed_trades)}")
                print(f"Win Rate:     {(closed_trades['pnl'] > 0).mean()*100:.1f}%")
                print(f"Total PnL:    {closed_trades['pnl'].sum():.2f}")
        print("="*45 + "\n")

def main():
    client = AngelOneClient()
    if not client.login(): return

    dc = DataCollector(client)
    now = datetime.now()
    from_date = (now - timedelta(days=2)).strftime("%Y-%m-%d 09:15")
    to_date = now.strftime("%Y-%m-%d %H:%M")
    
    logger.info("Finding best premium strikes (around 250)...")
    ce_match = dc.find_strike_by_premium("CE", 250)
    pe_match = dc.find_strike_by_premium("PE", 250)
    
    if not ce_match or not pe_match:
        logger.error("Could not identify option strikes.")
        return

    logger.info(f"CE: {ce_match['symbol']} | PE: {pe_match['symbol']}")
    
    logger.info("Fetching historical data...")
    df_idx = dc.get_historical_candles("NSE", "Nifty 50", "99926000", "FIVE_MINUTE", from_date, to_date)
    df_ce = dc.get_historical_candles("NFO", ce_match['symbol'], ce_match['token'], "FIVE_MINUTE", from_date, to_date)
    df_pe = dc.get_historical_candles("NFO", pe_match['symbol'], pe_match['token'], "FIVE_MINUTE", from_date, to_date)
    
    for df in [df_idx, df_ce, df_pe]:
        if df is not None:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            for col in ['open', 'high', 'low', 'close']: df[col] = pd.to_numeric(df[col])

    backtester = PatternBacktester()
    backtester.run(df_idx, df_ce, df_pe)

if __name__ == "__main__":
    main()
