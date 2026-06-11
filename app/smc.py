import pandas as pd
import numpy as np
from logzero import logger

class SMC:
    def __init__(self, df):
        """
        Initialize with OHLCV data.
        """
        self.df = df.copy()
        # Ensure column names are lowercase
        self.df.columns = [c.lower() for c in self.df.columns]

    def find_swings(self, window=5):
        """
        Identify local swing highs and lows using a rolling window.
        """
        self.df['swing_high'] = self.df['high'].rolling(window=window*2+1, center=True).max()
        self.df['swing_low'] = self.df['low'].rolling(window=window*2+1, center=True).min()
        
        self.df['is_swing_high'] = (self.df['high'] == self.df['swing_high'])
        self.df['is_swing_low'] = (self.df['low'] == self.df['swing_low'])
        return self.df

    def detect_structure(self):
        """
        Detect Break of Structure (BOS) and Change of Character (CHoCH).
        """
        self.df['bos'] = 0
        self.df['choch'] = 0
        self.df['market_trend'] = 0 # 1 for Bullish, -1 for Bearish
        
        last_high = None
        last_low = None
        current_trend = 0

        for i in range(len(self.df)):
            if self.df.iloc[i]['is_swing_high']:
                last_high = self.df.iloc[i]['high']
            if self.df.iloc[i]['is_swing_low']:
                last_low = self.df.iloc[i]['low']
            
            if last_high is None or last_low is None:
                continue

            close = self.df.iloc[i]['close']
            
            # Trend Detection & CHoCH
            if current_trend == 0:
                if close > last_high: current_trend = 1
                elif close < last_low: current_trend = -1
            elif current_trend == 1 and close < last_low:
                self.df.at[self.df.index[i], 'choch'] = -1
                current_trend = -1
            elif current_trend == -1 and close > last_high:
                self.df.at[self.df.index[i], 'choch'] = 1
                current_trend = 1
            
            # BOS (Continuation)
            elif current_trend == 1 and close > last_high:
                self.df.at[self.df.index[i], 'bos'] = 1
            elif current_trend == -1 and close < last_low:
                self.df.at[self.df.index[i], 'bos'] = -1
                
            self.df.at[self.df.index[i], 'market_trend'] = current_trend
            
        return self.df

    def detect_fvg(self):
        """
        Detects Fair Value Gaps (FVG).
        Bullish FVG: Low[i] > High[i-2]
        Bearish FVG: High[i] < Low[i-2]
        """
        self.df['fvg'] = 0
        self.df['fvg_top'] = np.nan
        self.df['fvg_bottom'] = np.nan

        for i in range(2, len(self.df)):
            # Bullish FVG
            if self.df['low'].iloc[i] > self.df['high'].iloc[i-2]:
                self.df.at[self.df.index[i], 'fvg'] = 1
                self.df.at[self.df.index[i], 'fvg_top'] = self.df['low'].iloc[i]
                self.df.at[self.df.index[i], 'fvg_bottom'] = self.df['high'].iloc[i-2]
            
            # Bearish FVG
            elif self.df['high'].iloc[i] < self.df['low'].iloc[i-2]:
                self.df.at[self.df.index[i], 'fvg'] = -1
                self.df.at[self.df.index[i], 'fvg_top'] = self.df['low'].iloc[i-2]
                self.df.at[self.df.index[i], 'fvg_bottom'] = self.df['high'].iloc[i]
        
        return self.df

    def detect_liquidity_sweep(self):
        """
        Detects Liquidity Sweeps.
        Bullish Sweep: Price goes below a previous Swing Low and closes back above it.
        """
        self.df['sweep'] = 0
        last_low = None
        last_high = None

        for i in range(1, len(self.df)):
            if self.df.iloc[i-1]['is_swing_low']:
                last_low = self.df.iloc[i-1]['low']
            if self.df.iloc[i-1]['is_swing_high']:
                last_high = self.df.iloc[i-1]['high']

            if last_low and self.df.iloc[i]['low'] < last_low and self.df.iloc[i]['close'] > last_low:
                self.df.at[self.df.index[i], 'sweep'] = 1
            
            if last_high and self.df.iloc[i]['high'] > last_high and self.df.iloc[i]['close'] < last_high:
                self.df.at[self.df.index[i], 'sweep'] = -1
        
        return self.df

    def find_order_blocks(self):
        """
        Identify Order Blocks: the last opposing candle before a structural break.
        """
        self.df['ob_bullish'] = np.nan
        self.df['ob_bearish'] = np.nan
        
        for i in range(1, len(self.df)):
            if self.df.iloc[i]['bos'] == 1 or self.df.iloc[i]['choch'] == 1:
                for j in range(i-1, 0, -1):
                    if self.df.iloc[j]['close'] < self.df.iloc[j]['open']:
                        self.df.at[self.df.index[i], 'ob_bullish'] = self.df.iloc[j]['low']
                        break
            
            if self.df.iloc[i]['bos'] == -1 or self.df.iloc[i]['choch'] == -1:
                for j in range(i-1, 0, -1):
                    if self.df.iloc[j]['close'] > self.df.iloc[j]['open']:
                        self.df.at[self.df.index[i], 'ob_bearish'] = self.df.iloc[j]['high']
                        break
        return self.df

if __name__ == "__main__":
    # Example usage with dummy data
    data = {
        'open':  [100, 102, 101, 105, 104, 110, 108, 107, 105, 103],
        'high':  [103, 105, 104, 112, 106, 115, 110, 108, 106, 104],
        'low':   [98,  100, 99,  103, 102, 108, 105, 104, 102, 100],
        'close': [102, 101, 104, 110, 105, 114, 107, 105, 103, 101]
    }
    df = pd.DataFrame(data)
    smc = SMC(df)
    df = smc.find_swings(window=2)
    df = smc.detect_structure()
    df = smc.detect_fvg()
    df = smc.detect_liquidity_sweep()
    df = smc.find_order_blocks()
    print(df[['close', 'market_trend', 'fvg', 'sweep', 'ob_bullish']])
