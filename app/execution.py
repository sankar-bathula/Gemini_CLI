from logzero import logger

class OrderExecutor:
    def __init__(self, client):
        """
        Initialize with an instance of AngelOneClient.
        """
        self.client = client

    def place_market_order(self, tradingsymbol, symboltoken, transaction_type, quantity, exchange="NSE", product_type="INTRADAY"):
        """
        Places a market order.
        """
        params = {
            "variety": "NORMAL",
            "tradingsymbol": tradingsymbol,
            "symboltoken": symboltoken,
            "transactiontype": transaction_type.upper(),
            "exchange": exchange,
            "ordertype": "MARKET",
            "producttype": product_type,
            "duration": "DAY",
            "quantity": str(quantity)
        }
        try:
            order_id = self.client.smart_api.placeOrder(params)
            logger.info(f"Market Order Placed: {order_id}")
            return order_id
        except Exception as e:
            logger.error(f"Error placing market order: {str(e)}")
            return None

    def place_sl_order(self, tradingsymbol, symboltoken, transaction_type, quantity, trigger_price, price=None, exchange="NSE", product_type="INTRADAY"):
        """
        Places a Stop Loss Market (SL-M) or Stop Loss Limit (SL-L) order.
        """
        order_type = "STOPLOSS_LIMIT" if price else "STOPLOSS_MARKET"
        params = {
            "variety": "STOPLOSS",
            "tradingsymbol": tradingsymbol,
            "symboltoken": symboltoken,
            "transactiontype": transaction_type.upper(),
            "exchange": exchange,
            "ordertype": order_type,
            "producttype": product_type,
            "duration": "DAY",
            "triggerprice": str(trigger_price),
            "quantity": str(quantity)
        }
        if price:
            params["price"] = str(price)

        try:
            order_id = self.client.smart_api.placeOrder(params)
            logger.info(f"SL Order Placed: {order_id} ({order_type})")
            return order_id
        except Exception as e:
            logger.error(f"Error placing SL order: {str(e)}")
            return None

if __name__ == "__main__":
    print("Order Executor module loaded.")
