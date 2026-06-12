from app.trend import TrendAnalyzer
from app.smc import SMC
from logzero import logger
import pandas as pd

class TradingStrategy:
    def __init__(self):
        self.data_1h = None
        self.data_15m = None
        self.data_5m = None
        self.data_1m = None

    def update_data(self, df_1h, df_15m, df_5m, df_1m):
        self.data_1h = df_1h
        self.data_15m = df_15m
        self.data_5m = df_5m
        self.data_1m = df_1m

    def generate_signal(self):
        """
        Multi-timeframe Signal Generation with SMC Triggers:
        1. 1H - Determine macro bias.
        2. 15 Min - Determine overall market Trend (Bullish/Bearish).
        3. 5 Min - Look for SMC Setup:
           - Alignment with Macro/15m Trend.
           - Presence of a Liquidity Sweep OR Price inside an FVG.
        4. 1 Min - Find precise Entry trigger.
        """
        if self.data_1h is None or self.data_15m is None or self.data_5m is None or self.data_1m is None:
            return "HOLD"

        # 1. 1H Macro Bias
        trend_1h = TrendAnalyzer(self.data_1h)
        trend_1h.calculate_indicators()
        bias_1h = trend_1h.get_trend_signal()

        # 2. 15 Min Trend
        trend_15m = TrendAnalyzer(self.data_15m)
        trend_15m.calculate_indicators()
        bias_15m = trend_15m.get_trend_signal() # 1 for Bull, -1 for Bear

        if bias_15m == 0:
            return "HOLD"

        # 3. 5 Min SMC Setup
        smc_5m = SMC(self.data_5m)
        smc_5m.find_swings()
        smc_5m.detect_structure()
        smc_5m.detect_fvg()
        smc_5m.detect_liquidity_sweep()
        
        last_5m = smc_5m.df.iloc[-1]
        
        # Check alignment with 15m trend (Macro 1H is optional for more trades)
        if last_5m['market_trend'] != bias_15m:
            return "HOLD"

        # Check for SMC Triggers (Sweep or FVG)
        # We look back 3 candles for a trigger to be less "same-candle" dependent
        recent_5m = smc_5m.df.tail(3)
        has_setup_trigger = False
        
        if bias_15m == 1: # Bullish
            is_bullish_sweep = (recent_5m['sweep'] == 1).any()
            is_in_fvg = (recent_5m['fvg'] == 1).any() or \
                        (not pd.isna(last_5m['fvg_bottom']) and last_5m['close'] >= last_5m['fvg_bottom'] * 0.999)
            if is_bullish_sweep or is_in_fvg:
                has_setup_trigger = True
        elif bias_15m == -1: # Bearish
            is_bearish_sweep = (recent_5m['sweep'] == -1).any()
            is_in_fvg = (recent_5m['fvg'] == -1).any() or \
                         (not pd.isna(last_5m['fvg_top']) and last_5m['close'] <= last_5m['fvg_top'] * 1.001)
            if is_bearish_sweep or is_in_fvg:
                has_setup_trigger = True

        if not has_setup_trigger:
            return "HOLD"

        # 4. 1 Min Entry
        trend_1m = TrendAnalyzer(self.data_1m)
        trend_1m.calculate_indicators()
        last_1m = trend_1m.df.iloc[-1]

        # Use EMA 9 crossing or just price position
        if bias_15m == 1:
            if last_1m['close'] > last_1m['ema_9']:
                logger.debug(f"SIGNAL: BUY triggered at {last_1m['close']}")
                return "BUY"
        elif bias_15m == -1:
            if last_1m['close'] < last_1m['ema_9']:
                logger.debug(f"SIGNAL: SELL triggered at {last_1m['close']}")
                return "SELL"

        return "HOLD"

if __name__ == "__main__":
    import pandas as pd # Needed for is_in_fvg check
    print("Strategy module loaded.")

if __name__ == "__main__":
    # Example usage would require real or more extensive dummy data
    print("Strategy module loaded.")
