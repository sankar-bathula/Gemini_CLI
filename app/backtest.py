import pandas as pd
from logzero import logger
from app.strategy import TradingStrategy
from app.risk import RiskManager
from datetime import datetime, timedelta

class BacktestEngine:
    def __init__(self, initial_balance=100000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.trades = []
        self.strategy = TradingStrategy()
        self.risk_manager = RiskManager()

    def run(self, df_1h, df_15m, df_5m, df_1m):
        """
        Runs the backtest by iterating through the 1m data and 
        periodically updating 5m, 15m and 1h contexts.
        """
        logger.info(f"Starting backtest with initial balance: {self.initial_balance}")
        
        active_trade = None
        
        # We start from index 500 to ensure indicators are primed
        for i in range(500, len(df_1m)):
            current_time = df_1m.index[i]
            current_price = df_1m.iloc[i]['close']
            
            # 1. Manage Active Trade
            if active_trade:
                # Check SL/TP
                hit_sl = False
                hit_tp = False
                if active_trade['side'] == 'BUY':
                    if current_price <= active_trade['sl']: hit_sl = True
                    elif current_price >= active_trade['tp']: hit_tp = True
                else:
                    if current_price >= active_trade['sl']: hit_sl = True
                    elif current_price <= active_trade['tp']: hit_tp = True

                if hit_sl:
                    self._close_trade(active_trade, active_trade['sl'], current_time, "STOP_LOSS")
                    active_trade = None
                elif hit_tp:
                    self._close_trade(active_trade, active_trade['tp'], current_time, "TAKE_PROFIT")
                    active_trade = None
                continue 

            # 2. Get available data slices (avoiding look-ahead bias)
            hist_1m = df_1m.iloc[:i+1].tail(500)
            hist_5m = df_5m[df_5m.index <= current_time].tail(200)
            hist_15m = df_15m[df_15m.index <= current_time].tail(200)
            hist_1h = df_1h[df_1h.index <= current_time].tail(200)

            if len(hist_15m) < 50 or len(hist_1h) < 20: continue

            # 3. Generate Signal
            self.strategy.update_data(hist_1h, hist_15m, hist_5m, hist_1m)
            signal = self.strategy.generate_signal()

            # 4. Execute Virtual Trade
            if signal != "HOLD":
                sl, tp = self.risk_manager.get_sl_tp_levels(current_price, signal)
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
                    logger.debug(f"Backtest: {signal} at {current_price} on {current_time}")

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
            print("No trades executed during backtest.")
            return

        df_trades = pd.DataFrame(self.trades)
        total_pnl = df_trades['pnl'].sum()
        win_rate = (df_trades['pnl'] > 0).mean() * 100
        
        print("\n--- Backtest Results ---")
        print(f"Total Trades: {len(df_trades)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Total PnL: {total_pnl:.2f}")
        print(f"Final Balance: {self.balance:.2f}")
        print(f"Profit Factor: {abs(df_trades[df_trades['pnl'] > 0]['pnl'].sum() / df_trades[df_trades['pnl'] < 0]['pnl'].sum()):.2f}")
        print("------------------------\n")

if __name__ == "__main__":
    # Example setup for backtesting (would require actual historical data)
    print("Backtest Engine loaded.")
