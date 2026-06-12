import pandas as pd
import numpy as np
from logzero import logger
from app.smc import SMC
from app.trend import TrendAnalyzer

from app.greeks import GreeksCalculator

class NiftySMCStrategy:
    """
    Advanced Multi-Timeframe SMC Strategy with Option Metrics:
    1. Trend Identification: 1H Chart for Bias.
    2. Zone Mapping: 15M Chart for S/R and Liquidity.
    3. Option Filters: PCR and OI-based S/R levels.
    4. Confirmation: BOS/CHoCH on 15M inside the zones.
    5. Entry: Retest of Order Block or FVG.
    """
    def __init__(self, rr_ratio=2.5):
        self.rr_ratio = rr_ratio
        self.bias_1h = 0
        self.zones_15m = {'support': [], 'resistance': [], 'liquidity': []}
        self.pcr = 0
        self.oi_support = 0
        self.oi_resistance = 0

    def update_bias(self, df_1h):
        """
        Determines the 1H Trend Bias.
        """
        trend = TrendAnalyzer(df_1h)
        trend.calculate_indicators()
        self.bias_1h = trend.get_trend_signal()
        return self.bias_1h

    def update_zones(self, df_15m):
        """
        Marks Support, Resistance, and Liquidity zones on 15M.
        """
        smc = SMC(df_15m)
        smc.find_swings(window=10)
        smc.detect_liquidity_sweep()
        smc.detect_structure() # Crucial: Detect structure before finding order blocks
        smc.find_order_blocks()
        
        # S/R from recent swings
        swings = smc.df[smc.df['is_swing_high'] | smc.df['is_swing_low']].tail(10)
        self.zones_15m['support'] = swings[swings['is_swing_low']]['low'].tolist()
        self.zones_15m['resistance'] = swings[swings['is_swing_high']]['high'].tolist()
        
        # Liquidity zones (un-swept swings)
        self.zones_15m['liquidity'] = smc.df[smc.df['sweep'] != 0]['low'].tail(5).tolist()
        
        return smc.df

    def update_option_metrics(self, df_chain, pcr, support, resistance):
        """
        Updates the strategy with live option chain metrics.
        """
        self.pcr = pcr
        self.oi_support = support
        self.oi_resistance = resistance

    def generate_signal(self, df_15m):
        """
        Generates signal considering structural and option data.
        """
        if self.bias_1h == 0:
            logger.debug("HOLD: Neutral 1H Bias")
            return "HOLD", None, None

        smc = SMC(df_15m)
        smc.find_swings(window=5)
        smc.detect_structure()
        smc.detect_fvg()
        smc.find_order_blocks()
        
        last_row = smc.df.iloc[-1]
        prev_row = smc.df.iloc[-2]
        proximity = last_row['close'] * 0.0015 # Slightly increased proximity
        
        # Doji Detection
        body_size = abs(last_row['close'] - last_row['open'])
        candle_range = (last_row['high'] - last_row['low']) if (last_row['high'] - last_row['low']) > 0 else 0.01
        is_doji = (body_size / candle_range) <= 0.15

        # Bullish Logic
        if self.bias_1h == 1:
            # Filter 1: PCR should be bullish (> 0.9)
            if self.pcr < 0.9:
                logger.debug(f"HOLD: PCR {self.pcr} not bullish enough (<0.9)")
                return "HOLD", None, None
            
            # Filter 2: Price near SMC Support OR OI Support OR recent BOS/CHoCH
            near_smc_support = any(abs(last_row['close'] - s) <= proximity for s in self.zones_15m['support'])
            near_oi_support = abs(last_row['close'] - self.oi_support) <= proximity * 2
            
            # Confirmation: Doji breakout OR BOS/CHoCH
            structural_conf = last_row['bos'] == 1 or last_row['choch'] == 1 or (smc.df['bos'].tail(3) == 1).any()
            doji_breakout = is_doji and last_row['close'] > prev_row['high']
            
            if (near_smc_support or near_oi_support) and (structural_conf or doji_breakout):
                sl = smc.df['low'].tail(5).min() - 2
                tp = last_row['close'] + (abs(last_row['close'] - sl) * self.rr_ratio)
                logger.info(f"SIGNAL: BUY triggered at {last_row['close']} | SL: {sl} | TP: {tp}")
                return "BUY", sl, tp

        # Bearish Logic
        elif self.bias_1h == -1:
            # Filter 1: PCR should be bearish (< 1.1)
            if self.pcr > 1.1:
                logger.debug(f"HOLD: PCR {self.pcr} not bearish enough (>1.1)")
                return "HOLD", None, None
            
            # Filter 2: Price near SMC Resistance OR OI Resistance
            near_smc_res = any(abs(last_row['close'] - r) <= proximity for r in self.zones_15m['resistance'])
            near_oi_res = abs(last_row['close'] - self.oi_resistance) <= proximity * 2
            
            structural_conf = last_row['bos'] == -1 or last_row['choch'] == -1 or (smc.df['bos'].tail(3) == -1).any()
            doji_breakout = is_doji and last_row['close'] < prev_row['low']

            if (near_smc_res or near_oi_res) and (structural_conf or doji_breakout):
                sl = smc.df['high'].tail(5).max() + 2
                tp = last_row['close'] - (abs(last_row['close'] - sl) * self.rr_ratio)
                logger.info(f"SIGNAL: SELL triggered at {last_row['close']} | SL: {sl} | TP: {tp}")
                return "SELL", sl, tp

        return "HOLD", None, None

if __name__ == "__main__":
    print("Multi-Timeframe SMC Strategy loaded.")
