import pandas as pd
import numpy as np
from logzero import logger

class PatternDetector:
    @staticmethod
    def is_hammer(row):
        """
        Hammer: Small body at the upper end of the range, long lower wick.
        """
        body_size = abs(row['close'] - row['open'])
        total_range = row['high'] - row['low']
        if total_range == 0: return False
        
        lower_wick = min(row['open'], row['close']) - row['low']
        upper_wick = row['high'] - max(row['open'], row['close'])
        
        # Lower wick at least 2x body, very small upper wick
        return lower_wick > (2 * body_size) and upper_wick < (0.1 * total_range)

    @staticmethod
    def is_shooting_star(row):
        """
        Shooting Star: Small body at the lower end of the range, long upper wick.
        """
        body_size = abs(row['close'] - row['open'])
        total_range = row['high'] - row['low']
        if total_range == 0: return False
        
        upper_wick = row['high'] - max(row['open'], row['close'])
        lower_wick = min(row['open'], row['close']) - row['low']
        
        # Upper wick at least 2x body, very small lower wick
        return upper_wick > (2 * body_size) and lower_wick < (0.1 * total_range)

    @staticmethod
    def is_engulfing(prev_row, curr_row):
        """
        Bullish Engulfing: 1 for Bullish, -1 for Bearish, 0 for None.
        """
        # Bullish Engulfing
        if prev_row['close'] < prev_row['open'] and \
           curr_row['close'] > curr_row['open'] and \
           curr_row['open'] < prev_row['close'] and \
           curr_row['close'] > prev_row['open']:
            return 1
        
        # Bearish Engulfing
        if prev_row['close'] > prev_row['open'] and \
           curr_row['close'] < curr_row['open'] and \
           curr_row['open'] > prev_row['close'] and \
           curr_row['close'] < prev_row['open']:
            return -1
        
        return 0

    @staticmethod
    def is_doji(row, threshold=0.1):
        body_size = abs(row['close'] - row['open'])
        total_range = row['high'] - row['low']
        if total_range == 0: return False
        return (body_size / total_range) <= threshold

    @staticmethod
    def is_inside_bar(prev_row, curr_row):
        """
        Inside Bar: Current candle is completely within the previous candle's range.
        """
        return curr_row['high'] <= prev_row['high'] and curr_row['low'] >= prev_row['low']

    @staticmethod
    def is_morning_star(r1, r2, r3):
        """
        Morning Star: 3-candle bullish reversal.
        1. Large bearish candle.
        2. Small candle (star).
        3. Large bullish candle.
        """
        is_r1_bearish = r1['close'] < r1['open']
        is_r3_bullish = r3['close'] > r3['open']
        is_r2_small = abs(r2['close'] - r2['open']) < (abs(r1['close'] - r1['open']) * 0.3)
        
        return is_r1_bearish and is_r3_bullish and is_r2_small and r3['close'] > (r1['open'] + r1['close'])/2

class PatternStrategy:
    def __init__(self, rr_ratio=2.5):
        self.rr_ratio = rr_ratio
        self.detector = PatternDetector()

    def generate_signal(self, df_idx, df_opt):
        """
        Combines Index patterns with Premium confirmation.
        """
        if len(df_idx) < 5 or len(df_opt) < 5:
            return "HOLD", None, None

        idx_curr = df_idx.iloc[-1]
        idx_prev = df_idx.iloc[-2]
        opt_curr = df_opt.iloc[-1]
        opt_prev = df_opt.iloc[-2]

        # 1. Detection on Index
        idx_bullish = False
        idx_bearish = False
        
        if self.detector.is_hammer(idx_curr) or self.detector.is_engulfing(idx_prev, idx_curr) == 1:
            idx_bullish = True
        
        if self.detector.is_shooting_star(idx_curr) or self.detector.is_engulfing(idx_prev, idx_curr) == -1:
            idx_bearish = True

        # 2. Premium Confirmation (Price Action in the Option itself)
        # Check if the premium is breaking out of its previous candle high/low
        if idx_bullish:
            if opt_curr['close'] > opt_prev['high']:
                sl = opt_curr['low'] - (opt_curr['close'] * 0.05) # 5% SL on premium
                tp = opt_curr['close'] + (abs(opt_curr['close'] - sl) * self.rr_ratio)
                return "BUY", sl, tp
        
        if idx_bearish:
            # Note: We usually "BUY" the Put option when index is bearish
            if opt_curr['close'] > opt_prev['high']:
                sl = opt_curr['low'] - (opt_curr['close'] * 0.05)
                tp = opt_curr['close'] + (abs(opt_curr['close'] - sl) * self.rr_ratio)
                return "SELL", sl, tp # Logic: SELL the index = BUY the PE

        return "HOLD", None, None

if __name__ == "__main__":
    print("Pattern Strategy module loaded.")
