import pandas as pd
from app.angel_api import AngelOneClient
from app.data_collector import DataCollector
from app.doji_strategy import DojiSRStrategy
from app.risk import RiskManager
from logzero import logger
from datetime import datetime, timedelta

class DojiBacktester:
    def __init__(self, initial_balance=100000, rr_ratio=2.0):
        self.balance = initial_balance
        self.trades = []
        self.strategy = DojiSRStrategy(rr_ratio=rr_ratio)
        self.risk_manager = RiskManager()

    def run(self, df):
        logger.info(f"Starting Doji S/R backtest on {len(df)} candles...")
        
        active_trade = None
        
        # Start after enough data to calculate S/R
        for i in range(50, len(df)):
            current_time = df.index[i]
            current_row = df.iloc[i]
            current_price = current_row['close']
            
            # 1. Manage Active Trade
            if active_trade:
                if (active_trade['side'] == 'BUY' and current_row['low'] <= active_trade['sl']) or \
                   (active_trade['side'] == 'SELL' and current_row['high'] >= active_trade['sl']):
                    self._close_trade(active_trade, active_trade['sl'], current_time, "STOP_LOSS")
                    active_trade = None
                elif (active_trade['side'] == 'BUY' and current_row['high'] >= active_trade['tp']) or \
                     (active_trade['side'] == 'SELL' and current_row['low'] <= active_trade['tp']):
                    self._close_trade(active_trade, active_trade['tp'], current_time, "TAKE_PROFIT")
                    active_trade = None
                continue

            # 2. Update Strategy and Generate Signal
            hist_df = df.iloc[:i+1]
            self.strategy.update_data(hist_df)
            signal, strat_sl, strat_tp = self.strategy.generate_signal()

            # 3. Execute Trade
            if signal != "HOLD":
                sl, tp = self.risk_manager.get_sl_tp_levels(current_price, signal, strategy_sl=strat_sl, strategy_tp=strat_tp)
                qty = self.risk_manager.calculate_position_size(self.balance, current_price, sl)
                
                if qty > 0:
                    active_trade = {
                        'side': signal,
                        'entry_price': current_price,
                        'entry_time': current_time,
                        'sl': sl,
                        'tp': tp,
                        'qty': qty
                    }
                    logger.debug(f"Trade: {signal} at {current_price} | SL: {sl} | TP: {tp}")

        self._print_results()

    def _close_trade(self, trade, exit_price, exit_time, reason):
        pnl = (exit_price - trade['entry_price']) * trade['qty']
        if trade['side'] == 'SELL':
            pnl = -pnl
        
        self.balance += pnl
        self.trades.append({
            **trade,
            'exit_price': exit_price,
            'exit_time': exit_time,
            'pnl': pnl,
            'reason': reason
        })

    def _print_results(self):
        if not self.trades:
            print("\nNo trades executed during backtest.")
            return

        df_trades = pd.DataFrame(self.trades)
        total_pnl = df_trades['pnl'].sum()
        win_rate = (df_trades['pnl'] > 0).mean() * 100
        
        print("\n" + "="*40)
        print(" DOJI S/R STRATEGY RESULTS ")
        print("="*40)
        print(f"Total Trades: {len(df_trades)}")
        print(f"Win Rate:     {win_rate:.2f}%")
        print(f"Total PnL:    {total_pnl:.2f}")
        print(f"Final Balance: {self.balance:.2f}")
        if len(df_trades[df_trades['pnl'] < 0]) > 0:
            loss = abs(df_trades[df_trades['pnl'] < 0]['pnl'].sum())
            profit = df_trades[df_trades['pnl'] > 0]['pnl'].sum()
            print(f"Profit Factor: {profit/loss:.2f}")
        print("="*40 + "\n")

def main():
    client = AngelOneClient()
    if not client.login(): return

    collector = DataCollector(client)
    days = 30
    to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    
    # NIFTY 5m timeframe
    df = collector.get_historical_candles("NSE", "Nifty 50", "99926000", "FIVE_MINUTE", from_date, to_date)
    
    if df is not None and not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        backtester = DojiBacktester(rr_ratio=2.0)
        backtester.run(df)

if __name__ == "__main__":
    main()
