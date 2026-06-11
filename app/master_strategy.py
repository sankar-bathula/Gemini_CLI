import pandas as pd
import numpy as np
from logzero import logger
from app.smc import SMC
from app.trend import TrendAnalyzer

class NiftyMasterStrategy:
    """
    Nifty Master Strategy:
    - Combines SMC (Liquidity Sweeps, FVG) with Candle Patterns (Doji).
    - Uses High-Probability Support/Resistance triggers.
    - Optimized for Nifty 50 on 5-minute timeframe.
    """
    def __init__(self, doji_threshold=0.15, rr_ratio=2.5):
        self.doji_threshold = doji_threshold
        self.rr_ratio = rr_ratio
        self.data = None

    def update_data(self, df):
        self.data = df.copy()
        self.data.columns = [c.lower() for c in self.data.columns]

    def generate_signal(self):
        if self.data is None or len(self.data) < 50:
            return "HOLD", None, None

        # 1. SMC Analysis
        smc = SMC(self.data)
        smc.find_swings(window=10)
        smc.detect_structure()
        smc.detect_liquidity_sweep()
        smc.detect_fvg()
        
        last_row = smc.df.iloc[-1]
        prev_row = smc.df.iloc[-2]
        
        # Time Filter: No trades in first 15 mins (9:15-9:30) or last 30 mins (15:00-15:30)
        # Assuming index is timestamp
        current_time = self.data.index[-1]
        if hasattr(current_time, 'time'):
            t = current_time.time()
            if t < pd.Timestamp("09:45").time() or t > pd.Timestamp("15:00").time():
                return "HOLD", None, None

        # 2. Doji Detection on Previous Candle
        body_size = abs(prev_row['close'] - prev_row['open'])
        candle_range = prev_row['high'] - prev_row['low']
        is_doji = (body_size / max(candle_range, 0.001)) <= self.doji_threshold

        if not is_doji:
            return "HOLD", None, None

        # 3. Strategy Triggers
        # BULLISH: SMC Bullish Sweep OR tap into Bullish FVG + Break of Doji High
        if last_row['close'] > prev_row['high']:
            # Check for bullish context in recent candles (prev 3)
            recent = smc.df.iloc[-5:-1]
            has_bull_context = (recent['sweep'] == 1).any() or (recent['fvg'] == 1).any()
            
            if has_bull_context:
                sl = prev_row['low'] - 2 # 2 point buffer
                risk = last_row['close'] - sl
                if risk > 5: # Minimum risk floor
                    tp = last_row['close'] + (risk * self.rr_ratio)
                    return "BUY", sl, tp

        # BEARISH: SMC Bearish Sweep OR tap into Bearish FVG + Break of Doji Low
        if last_row['close'] < prev_row['low']:
            recent = smc.df.iloc[-5:-1]
            has_bear_context = (recent['sweep'] == -1).any() or (recent['fvg'] == -1).any()
            
            if has_bear_context:
                sl = prev_row['high'] + 2 # 2 point buffer
                risk = sl - last_row['close']
                if risk > 5:
                    tp = last_row['close'] - (risk * self.rr_ratio)
                    return "SELL", sl, tp

        return "HOLD", None, None

if __name__ == "__main__":
    print("Master Strategy module loaded.")
