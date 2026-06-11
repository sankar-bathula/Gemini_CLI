from app.trend import TrendAnalyzer
from app.smc import SMC
from logzero import logger

class TradingStrategy:
    def __init__(self):
        self.data_15m = None
        self.data_5m = None
        self.data_1m = None

    def update_data(self, df_15m, df_5m, df_1m):
        self.data_15m = df_15m
        self.data_5m = df_5m
        self.data_1m = df_1m

    def generate_signal(self):
        """
        Multi-timeframe Signal Generation with SMC Triggers:
        1. 15 Min - Determine overall market Trend (Bullish/Bearish).
        2. 5 Min - Look for SMC Setup:
           - Alignment with 15m Trend.
           - Presence of a Liquidity Sweep OR Price inside an FVG.
        3. 1 Min - Find precise Entry trigger.
        """
        if self.data_15m is None or self.data_5m is None or self.data_1m is None:
            return "HOLD"

        # 1. 15 Min Trend
        trend_15m = TrendAnalyzer(self.data_15m)
        trend_15m.calculate_indicators()
        bias_15m = trend_15m.get_trend_signal() # 1 for Bull, -1 for Bear

        if bias_15m == 0:
            return "HOLD"

        # 2. 5 Min SMC Setup
        smc_5m = SMC(self.data_5m)
        smc_5m.find_swings()
        smc_5m.detect_structure()
        smc_5m.detect_fvg()
        smc_5m.detect_liquidity_sweep()
        
        last_5m = smc_5m.df.iloc[-1]
        
        # Check alignment with 15m trend
        if last_5m['market_trend'] != bias_15m:
            return "HOLD"

        # Check for SMC Triggers (Sweep or FVG)
        has_setup_trigger = False
        if bias_15m == 1: # Bullish
            # Bullish Sweep or currently in a Bullish FVG
            is_bullish_sweep = last_5m['sweep'] == 1
            is_in_fvg = last_5m['fvg'] == 1 or (not pd.isna(last_5m['fvg_bottom']) and last_5m['close'] >= last_5m['fvg_bottom'] and last_5m['close'] <= last_5m['fvg_top'])
            if is_bullish_sweep or is_in_fvg:
                has_setup_trigger = True
        elif bias_15m == -1: # Bearish
            # Bearish Sweep or currently in a Bearish FVG
            is_bearish_sweep = last_5m['sweep'] == -1
            is_in_fvg = last_5m['fvg'] == -1 or (not pd.isna(last_5m['fvg_top']) and last_5m['close'] <= last_5m['fvg_top'] and last_5m['close'] >= last_5m['fvg_bottom'])
            if is_bearish_sweep or is_in_fvg:
                has_setup_trigger = True

        if not has_setup_trigger:
            return "HOLD"

        # 3. 1 Min Entry
        trend_1m = TrendAnalyzer(self.data_1m)
        trend_1m.calculate_indicators()
        last_1m = trend_1m.df.iloc[-1]

        if bias_15m == 1:
            if last_1m['close'] > last_1m['ema_9']:
                return "BUY"
        elif bias_15m == -1:
            if last_1m['close'] < last_1m['ema_9']:
                return "SELL"

        return "HOLD"

if __name__ == "__main__":
    import pandas as pd # Needed for is_in_fvg check
    print("Strategy module loaded.")

if __name__ == "__main__":
    # Example usage would require real or more extensive dummy data
    print("Strategy module loaded.")
