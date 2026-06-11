from logzero import logger

class RiskManager:
    def __init__(self, risk_per_trade=0.01, default_stop_loss_pct=0.02, default_take_profit_pct=0.04):
        """
        Initialize with risk parameters.
        :param risk_per_trade: Percentage of capital to risk per trade (e.g., 0.01 = 1%)
        :param default_stop_loss_pct: Stop loss as a percentage of entry price.
        :param default_take_profit_pct: Take profit as a percentage of entry price.
        """
        self.risk_per_trade = risk_per_trade
        self.default_stop_loss_pct = default_stop_loss_pct
        self.default_take_profit_pct = default_take_profit_pct

    def calculate_position_size(self, balance, entry_price, stop_loss_price):
        """
        Calculate quantity based on fixed fractional risk.
        Quantity = (Balance * Risk%) / (Entry Price - Stop Loss Price)
        """
        try:
            risk_amount = balance * self.risk_per_trade
            risk_per_share = abs(entry_price - stop_loss_price)
            
            if risk_per_share == 0:
                return 0
            
            quantity = int(risk_amount / risk_per_share)
            return max(quantity, 0)
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 0

    def get_sl_tp_levels(self, entry_price, side, strategy_sl=None, strategy_tp=None, rr_ratio=None):
        """
        Calculate Stop Loss and Take Profit levels. 
        Prioritizes strategy-provided levels, falls back to percentages.
        """
        if strategy_sl is not None:
            sl = strategy_sl
            if strategy_tp is not None:
                tp = strategy_tp
            elif rr_ratio is not None:
                risk = abs(entry_price - sl)
                if side.upper() == "BUY":
                    tp = entry_price + (risk * rr_ratio)
                else:
                    tp = entry_price - (risk * rr_ratio)
            else:
                # Fallback TP if only SL is provided
                tp = entry_price * (1 + self.default_take_profit_pct) if side.upper() == "BUY" else entry_price * (1 - self.default_take_profit_pct)
        else:
            # Traditional percentage-based SL/TP
            if side.upper() == "BUY":
                sl = entry_price * (1 - self.default_stop_loss_pct)
                tp = entry_price * (1 + self.default_take_profit_pct)
            else:
                sl = entry_price * (1 + self.default_stop_loss_pct)
                tp = entry_price * (1 - self.default_take_profit_pct)
        
        return round(float(sl), 2), round(float(tp), 2)

if __name__ == "__main__":
    rm = RiskManager()
    balance = 100000
    entry = 500
    sl, tp = rm.get_sl_tp_levels(entry, "BUY")
    qty = rm.calculate_position_size(balance, entry, sl)
    print(f"Balance: {balance}, Entry: {entry}, SL: {sl}, TP: {tp}, Qty: {qty}")
