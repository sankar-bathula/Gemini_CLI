import pandas as pd
import numpy as np
from app.master_strategy import NiftyMasterStrategy
from app.smc import SMC
from logzero import logger

def run_yearly_backtest(csv_path="nifty_50_1year_five_minute.csv"):
    logger.info(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    strategy = NiftyMasterStrategy(rr_ratio=3.0) # Aiming for 1:3 RR for the "Best" strategy
    
    balance = 100000
    trades = []
    active_trade = None
    
    logger.info(f"Pre-calculating indicators for {len(df)} candles...")
    smc = SMC(df)
    smc.find_swings(window=10)
    smc.detect_structure()
    smc.detect_liquidity_sweep()
    smc.detect_fvg()
    df_ind = smc.df
    
    # Doji Detection (vectorized)
    body_size = abs(df_ind['close'] - df_ind['open'])
    candle_range = (df_ind['high'] - df_ind['low']).replace(0, 0.001)
    df_ind['is_doji'] = (body_size / candle_range) <= 0.15

    # EMA 200 for Trend Filter
    df_ind['ema_200'] = df_ind['close'].ewm(span=200, adjust=False).mean()

    logger.info(f"Starting yearly backtest...")
    
    for i in range(100, len(df_ind)):
        current_row = df_ind.iloc[i]
        prev_row = df_ind.iloc[i-1]
        current_time = df_ind.index[i]
        
        if active_trade:
            # ... (unchanged trade management)
            hit_sl = False
            hit_tp = False
            
            if active_trade['side'] == 'BUY':
                if current_row['low'] <= active_trade['sl']: hit_sl = True
                elif current_row['high'] >= active_trade['tp']: hit_tp = True
            else:
                if current_row['high'] >= active_trade['sl']: hit_sl = True
                elif current_row['low'] <= active_trade['tp']: hit_tp = True
            
            if hit_sl or hit_tp or current_time.time() >= pd.Timestamp("15:20").time():
                reason = "SL" if hit_sl else ("TP" if hit_tp else "EOD")
                exit_price = active_trade['sl'] if hit_sl else (active_trade['tp'] if hit_tp else current_row['close'])
                pnl = (exit_price - active_trade['entry_price']) if active_trade['side'] == 'BUY' else (active_trade['entry_price'] - exit_price)
                trades.append({**active_trade, 'exit_price': exit_price, 'exit_time': current_time, 'pnl': pnl, 'reason': reason})
                balance += pnl * 50
                active_trade = None
            continue

        # 2. Look for Signals
        t = current_time.time()
        if t < pd.Timestamp("09:45").time() or t > pd.Timestamp("14:30").time():
            continue

        # Signal Logic (Optimized with Trend Filter)
        if prev_row['is_doji']:
            # Bullish: Breakout + SMC + Trend (Price > EMA 200)
            if current_row['close'] > prev_row['high'] and current_row['close'] > current_row['ema_200']:
                recent = df_ind.iloc[i-5:i]
                if (recent['sweep'] == 1).any() or (recent['fvg'] == 1).any():
                    sl = prev_row['low'] - 2
                    risk = current_row['close'] - sl
                    if risk > 5:
                        active_trade = {'side': 'BUY', 'entry_price': current_row['close'], 'entry_time': current_time, 'sl': sl, 'tp': current_row['close'] + (risk * 3.0)}
            
            # Bearish: Breakout + SMC + Trend (Price < EMA 200)
            elif current_row['close'] < prev_row['low'] and current_row['close'] < current_row['ema_200']:
                recent = df_ind.iloc[i-5:i]
                if (recent['sweep'] == -1).any() or (recent['fvg'] == -1).any():
                    sl = prev_row['high'] + 2
                    risk = sl - current_row['close']
                    if risk > 5:
                        active_trade = {'side': 'SELL', 'entry_price': current_row['close'], 'entry_time': current_time, 'sl': sl, 'tp': current_row['close'] - (risk * 3.0)}

    # 3. Print Results
    if not trades:
        print("\nNo trades executed in the yearly backtest.")
        return

    df_t = pd.DataFrame(trades)
    total_points = df_t['pnl'].sum()
    win_rate = (df_t['pnl'] > 0).mean() * 100
    
    print("\n" + "="*50)
    print(" NIFTY YEARLY MASTER STRATEGY RESULTS ")
    print("="*50)
    print(f"Total Trades:  {len(df_t)}")
    print(f"Win Rate:      {win_rate:.2f}%")
    print(f"Total Points:  {total_points:.2f}")
    print(f"Profit Factor: {abs(df_t[df_t['pnl']>0]['pnl'].sum() / df_t[df_t['pnl']<0]['pnl'].sum()):.2f}")
    print(f"Avg Points/Trade: {total_points/len(df_t):.2f}")
    
    # Estimate Option PnL (assuming 0.5 delta)
    print(f"Est. Option PnL (50 qty): ₹{total_points * 0.5 * 50:,.2f}")
    print(f"Final Account Value: ₹{balance:,.2f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_yearly_backtest()
