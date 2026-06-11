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
        - EMA 20, 50, 200
        - ADX (Average Directional Index)
        - SuperTrend
        """
        try:
            # 1. EMAs
            self.df['ema_20'] = ta.ema(self.df['close'], length=20)
            self.df['ema_50'] = ta.ema(self.df['close'], length=50)
            self.df['ema_200'] = ta.ema(self.df['close'], length=200)

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
        - Bullish: Price > EMA 200 AND EMA 20 > EMA 50 AND SuperTrend is Bullish AND ADX > 20
        - Bearish: Price < EMA 200 AND EMA 20 < EMA 50 AND SuperTrend is Bearish AND ADX > 20
        """
        if len(self.df) < 200:
            return "NEUTRAL"

        last_row = self.df.iloc[-1]
        
        # Check for column availability (SuperTrend column names vary)
        st_dir_col = 'SUPERTd_10_3.0'
        adx_col = 'ADX_14'
        
        if st_dir_col not in last_row or adx_col not in last_row:
            logger.warning(f"Required indicator columns {st_dir_col} or {adx_col} missing.")
            return "NEUTRAL"

        is_adx_strong = last_row[adx_col] > 20
        is_ema_bullish = (last_row['close'] > last_row['ema_200']) and (last_row['ema_20'] > last_row['ema_50'])
        is_ema_bearish = (last_row['close'] < last_row['ema_200']) and (last_row['ema_20'] < last_row['ema_50'])
        is_st_bullish = last_row[st_dir_col] == 1
        is_st_bearish = last_row[st_dir_col] == -1

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
