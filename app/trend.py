import pandas as pd
import pandas_ta as ta
from logzero import logger

class TrendAnalyzer:
    def __init__(self, df):
        """
        Initialize with a pandas DataFrame containing OHLCV data.
        Required columns: 'open', 'high', 'low', 'close', 'volume'
        """
        self.df = df.copy()
        # Ensure column names are lowercase
        self.df.columns = [c.lower() for c in self.df.columns]

    def calculate_indicators(self):
        """
        Calculate indicators for trend detection:
        - EMA 9, 21, 50
        - ADX (Average Directional Index)
        - SuperTrend
        """
        try:
            # 1. EMAs
            self.df['ema_9'] = ta.ema(self.df['close'], length=9)
            self.df['ema_21'] = ta.ema(self.df['close'], length=21)
            self.df['ema_50'] = ta.ema(self.df['close'], length=50)

            # 2. ADX (Trend Strength)
            adx = ta.adx(self.df['high'], self.df['low'], self.df['close'], length=14)
            self.df = pd.concat([self.df, adx], axis=1)

            # 3. SuperTrend (Volatility-based Trend)
            st = ta.supertrend(self.df['high'], self.df['low'], self.df['close'], length=10, multiplier=3)
            self.df = pd.concat([self.df, st], axis=1)

            return self.df
        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            return self.df

    def get_market_direction(self):
        """
        Determine if the market is BULLISH, BEARISH, or NEUTRAL.
        Logic:
        - Bullish: Price > EMA 50 AND EMA 9 > EMA 21 AND SuperTrend is Bullish AND ADX > 20
        - Bearish: Price < EMA 50 AND EMA 9 < EMA 21 AND SuperTrend is Bearish AND ADX > 20
        """
        if len(self.df) < 50: # Reduced from 200 to 50 for earlier signaling
            return "NEUTRAL"

        last_row = self.df.iloc[-1]
        
        # Check for column availability (SuperTrend column names vary)
        st_dir_col = 'SUPERTd_10_3.0'
        adx_col = 'ADX_14'
        
        # Safe checks
        is_adx_strong = last_row.get(adx_col, 0) > 20
        is_st_bullish = last_row.get(st_dir_col, 0) == 1
        is_st_bearish = last_row.get(st_dir_col, 0) == -1
        
        ema_9 = last_row.get('ema_9', last_row['close'])
        ema_21 = last_row.get('ema_21', last_row['close'])
        ema_50 = last_row.get('ema_50', last_row['close']) 

        if pd.isna(ema_9): ema_9 = last_row['close']
        if pd.isna(ema_21): ema_21 = last_row['close']
        if pd.isna(ema_50): ema_50 = last_row['close']

        is_ema_bullish = (last_row['close'] > ema_50) and (ema_9 > ema_21)
        is_ema_bearish = (last_row['close'] < ema_50) and (ema_9 < ema_21)

        # Require at least EMAs if ADX/ST are missing due to short history
        if st_dir_col not in last_row:
            if is_ema_bullish: return "BULLISH"
            if is_ema_bearish: return "BEARISH"
            return "NEUTRAL"

        if is_ema_bullish and is_st_bullish and is_adx_strong:
            return "BULLISH"
        elif is_ema_bearish and is_st_bearish and is_adx_strong:
            return "BEARISH"
        
        return "NEUTRAL"

    def get_trend_signal(self):
        """
        Legacy method for compatibility. 
        Returns 1 for Bullish, -1 for Bearish, 0 for Neutral.
        """
        direction = self.get_market_direction()
        if direction == "BULLISH": return 1
        if direction == "BEARISH": return -1
        return 0

if __name__ == "__main__":
    # Test with dummy data
    import numpy as np
    dates = pd.date_range('2023-01-01', periods=250)
    data = np.random.randn(250).cumsum() + 100
    df = pd.DataFrame({
        'open': data, 'high': data+1, 'low': data-1, 'close': data, 'volume': 1000
    }, index=dates)
    
    analyzer = TrendAnalyzer(df)
    analyzer.calculate_indicators()
    direction = analyzer.get_market_direction()
    print(f"Detected Market Direction: {direction}")
