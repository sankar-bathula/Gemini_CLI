import pandas as pd
import numpy as np
from logzero import logger
from app.smc import SMC
from app.trend import TrendAnalyzer

class DojiSRStrategy:
    def __init__(self, doji_threshold=0.1, rr_ratio=2.0):
        """
        :param doji_threshold: Max body size as % of total candle range to consider it a Doji.
        :param rr_ratio: Risk-Reward ratio for Take Profit calculation.
        """
        self.doji_threshold = doji_threshold
        self.rr_ratio = rr_ratio
        self.data = None
        self.sr_levels = []

    def update_data(self, df):
        self.data = df.copy()
        self.data.columns = [c.lower() for c in self.data.columns]
        self._calculate_sr_levels()
        self._detect_doji()

    def _calculate_sr_levels(self):
        """
        Identify Support and Resistance levels using SMC swing highs/lows.
        """
        smc = SMC(self.data)
        smc.find_swings(window=10) # Using a larger window for more significant S/R
        
        # Extract recent significant swing highs (Resistance) and lows (Support)
        swings = smc.df[smc.df['is_swing_high'] | smc.df['is_swing_low']].tail(20)
        self.support_levels = swings[swings['is_swing_low']]['low'].tolist()
        self.resistance_levels = swings[swings['is_swing_high']]['high'].tolist()

    def _detect_doji(self):
        """
        Detect Doji candles where the body is very small compared to the range.
        """
        body_size = abs(self.data['close'] - self.data['open'])
        candle_range = self.data['high'] - self.data['low']
        
        # Avoid division by zero
        safe_range = candle_range.replace(0, 0.001)
        
        self.data['is_doji'] = (body_size / safe_range) <= self.doji_threshold
        return self.data

    def generate_signal(self):
        """
        Signal Logic:
        1. BUY: Price is near Support AND a Doji formed AND current price breaks Doji High.
        2. SELL: Price is near Resistance AND a Doji formed AND current price breaks Doji Low.
        """
        if self.data is None or len(self.data) < 2:
            return "HOLD", None, None

        last_row = self.data.iloc[-1]
        prev_row = self.data.iloc[-2]
        
        # Check if previous candle was a Doji
        if not prev_row['is_doji']:
            return "HOLD", None, None

        # Proximity threshold (e.g., within 0.1% of S/R)
        proximity = last_row['close'] * 0.002 

        # 1. Buy Signal (Near Support)
        is_near_support = any(abs(prev_row['low'] - s) <= proximity for s in self.support_levels)
        if is_near_support and last_row['close'] > prev_row['high']:
            sl = prev_row['low']
            risk = prev_row['high'] - sl
            tp = last_row['close'] + (risk * self.rr_ratio)
            return "BUY", sl, tp

        # 2. Sell Signal (Near Resistance)
        is_near_resistance = any(abs(prev_row['high'] - r) <= proximity for r in self.resistance_levels)
        if is_near_resistance and last_row['close'] < prev_row['low']:
            sl = prev_row['high']
            risk = sl - prev_row['low']
            tp = last_row['close'] - (risk * self.rr_ratio)
            return "SELL", sl, tp

        return "HOLD", None, None

    def get_premium_strike(self, spot_price, side):
        """
        Selects a premium strike (ATM or slightly ITM).
        For Nifty, strikes are in multiples of 50.
        """
        strike_step = 50
        atm_strike = round(spot_price / strike_step) * strike_step
        
        if side == "BUY":
            # For Buying Call: ATM or slightly ITM (lower strike)
            return int(atm_strike)
        else:
            # For Buying Put (Selling the Index): ATM or slightly ITM (higher strike)
            return int(atm_strike)

if __name__ == "__main__":
    # Test with dummy data
    data = {
        'open':  [100, 102, 104, 105.1, 106],
        'high':  [103, 105, 106, 105.2, 108],
        'low':   [98,  100, 102, 105.0, 104],
        'close': [102, 104, 105, 105.1, 107]
    }
    df = pd.DataFrame(data)
    strategy = DojiSRStrategy(doji_threshold=0.2)
    strategy.update_data(df)
    signal, sl, tp = strategy.generate_signal()
    print(f"Signal: {signal}, SL: {sl}, TP: {tp}")
