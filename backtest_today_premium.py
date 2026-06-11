import pandas as pd
import numpy as np
from app.angel_api import AngelOneClient
from app.data_collector import DataCollector
from app.doji_strategy import DojiSRStrategy
from app.risk import RiskManager
from logzero import logger
from datetime import datetime, timedelta

class PremiumBacktester:
    def __init__(self, initial_balance=100000):
        self.balance = initial_balance
        self.trades = []
        self.strategy = DojiSRStrategy(rr_ratio=2.0)
        self.risk_manager = RiskManager()

    def run(self, df_index, df_ce, df_pe, ce_token, pe_token):
        logger.info(f"Starting Today's Premium Backtest...")
        
        active_trade = None
        
        # Align data by timestamp
        # We'll use index as the master timeline
        for i in range(50, len(df_index)):
            current_time = df_index.index[i]
            idx_row = df_index.iloc[i]
            
            # 1. Manage Active Trade (using Option Prices)
            if active_trade:
                opt_df = df_ce if active_trade['option_type'] == 'CE' else df_pe
                if current_time in opt_df.index:
                    opt_row = opt_df.loc[current_time]
                    opt_price = opt_row['close']
                    
                    if opt_row['low'] <= active_trade['sl_opt']:
                        self._close_trade(active_trade, active_trade['sl_opt'], current_time, "STOP_LOSS")
                        active_trade = None
                    elif opt_row['high'] >= active_trade['tp_opt']:
                        self._close_trade(active_trade, active_trade['tp_opt'], current_time, "TAKE_PROFIT")
                        active_trade = None
                continue

            # 2. Update Strategy and Generate Signal (using Index)
            hist_idx = df_index.iloc[:i+1]
            self.strategy.update_data(hist_idx)
            signal, _, _ = self.strategy.generate_signal()

            # 3. Execute Trade (using Option Data)
            if signal != "HOLD":
                opt_type = "CE" if signal == "BUY" else "PE"
                opt_df = df_ce if opt_type == "CE" else df_pe
                
                if current_time in opt_df.index:
                    opt_row = opt_df.loc[current_time]
                    entry_premium = opt_row['close']
                    
                    # 20% SL on premium as implemented in main.py
                    sl_opt = entry_premium * 0.8
                    tp_opt = entry_premium * 1.4 # 1:2 RR on premium approx
                    
                    qty = (5000 // entry_premium // 50) * 50
                    
                    if qty > 0:
                        active_trade = {
                            'side': signal,
                            'option_type': opt_type,
                            'entry_price': entry_premium,
                            'entry_time': current_time,
                            'sl_opt': sl_opt,
                            'tp_opt': tp_opt,
                            'qty': qty
                        }
                        logger.debug(f"Trade: {opt_type} at {entry_premium} premium")

        self._print_results()

    def _close_trade(self, trade, exit_price, exit_time, reason):
        pnl = (exit_price - trade['entry_price']) * trade['qty']
        self.balance += pnl
        self.trades.append({
            **trade,
            'exit_price': exit_price,
            'exit_time': exit_time,
            'pnl': pnl,
            'reason': reason
        })

    def _print_results(self):
        print("\n" + "="*45)
        print(" TODAY'S PREMIUM BACKTEST RESULTS (NIFTY) ")
        print("="*45)
        if not self.trades:
            print("No trades triggered today.")
        else:
            df_t = pd.DataFrame(self.trades)
            for _, t in df_t.iterrows():
                print(f"{t['entry_time'].strftime('%H:%M')} | {t['option_type']} | Entry: {t['entry_price']:.1f} | Exit: {t['exit_price']:.1f} | PnL: {t['pnl']:.0f} ({t['reason']})")
            
            print("-"*45)
            print(f"Total Trades: {len(df_t)}")
            print(f"Win Rate:     {(df_t['pnl'] > 0).mean()*100:.1f}%")
            print(f"Total PnL:    {df_t['pnl'].sum():.2f}")
        print("="*45 + "\n")

def main():
    client = AngelOneClient()
    if not client.login(): return

    dc = DataCollector(client)
    now = datetime.now()
    # Fetch 5 days to prime S/R, focus on today's trades
    from_date = (now - timedelta(days=5)).strftime("%Y-%m-%d 09:15")
    to_date = now.strftime("%Y-%m-%d %H:%M")
    
    logger.info("Finding best premium strikes (around 250)...")
    ce_match = dc.find_strike_by_premium("CE", 250)
    pe_match = dc.find_strike_by_premium("PE", 250)
    
    if not ce_match or not pe_match:
        logger.error("Could not identify option strikes for backtest.")
        return

    logger.info(f"CE: {ce_match['symbol']} | PE: {pe_match['symbol']}")
    
    logger.info("Fetching historical data for Index and Options...")
    df_idx = dc.get_historical_candles("NSE", "Nifty 50", "99926000", "FIVE_MINUTE", from_date, to_date)
    df_ce = dc.get_historical_candles("NFO", ce_match['symbol'], ce_match['token'], "FIVE_MINUTE", from_date, to_date)
    df_pe = dc.get_historical_candles("NFO", pe_match['symbol'], pe_match['token'], "FIVE_MINUTE", from_date, to_date)
    
    for df in [df_idx, df_ce, df_pe]:
        if df is not None:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            for col in ['open', 'high', 'low', 'close']: df[col] = pd.to_numeric(df[col])

    # Filter index to today's market hours for report focus, but keep history for S/R
    backtester = PremiumBacktester()
    backtester.run(df_idx, df_ce, df_pe, ce_match['token'], pe_match['token'])

if __name__ == "__main__":
    main()
