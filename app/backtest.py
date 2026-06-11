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

    def run(self, df_15m, df_5m, df_1m):
        """
        Runs the backtest by iterating through the 1m data and 
        periodically updating 5m and 15m contexts.
        """
        logger.info(f"Starting backtest with initial balance: {self.initial_balance}")
        
        # Align data (Simplified: we assume df_1m is the master timeline)
        # In a real backtest, we would ensure look-ahead bias is avoided by only
        # showing the strategy data that would have been available at that specific 'now'.
        
        active_trade = None
        
        # We start from index 200 to ensure indicators are primed
        for i in range(200, len(df_1m)):
            current_time = df_1m.index[i]
            current_price = df_1m.iloc[i]['close']
            
            # 1. Manage Active Trade
            if active_trade:
                # Check SL/TP
                if (active_trade['side'] == 'BUY' and current_price <= active_trade['sl']) or \
                   (active_trade['side'] == 'SELL' and current_price >= active_trade['sl']):
                    self._close_trade(active_trade, current_price, current_time, "STOP_LOSS")
                    active_trade = None
                elif (active_trade['side'] == 'BUY' and current_price >= active_trade['tp']) or \
                     (active_trade['side'] == 'SELL' and current_price <= active_trade['tp']):
                    self._close_trade(active_trade, current_price, current_time, "TAKE_PROFIT")
                    active_trade = None
                continue # Only one active trade for simplicity

            # 2. Get available data slices (avoiding look-ahead bias)
            hist_1m = df_1m.iloc[:i+1].tail(500)
            hist_5m = df_5m[df_5m.index <= current_time].tail(200)
            hist_15m = df_15m[df_15m.index <= current_time].tail(200)

            if len(hist_15m) < 50: continue

            # 3. Generate Signal
            self.strategy.update_data(hist_15m, hist_5m, hist_1m)
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
