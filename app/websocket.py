from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from logzero import logger
import threading

class AngelOneWebSocket:
    def __init__(self, auth_token, api_key, client_code, feed_token):
        self.sws = SmartWebSocketV2(auth_token, api_key, client_code, feed_token)
        self.on_tick_callback = None
        
        # Assign callbacks
        self.sws.on_data = self._on_data
        self.sws.on_open = self._on_open
        self.sws.on_error = self._on_error
        self.sws.on_close = self._on_close

    def _on_data(self, wsapp, msg):
        """
        Internal callback for receiving tick data.
        """
        if self.on_tick_callback:
            self.on_tick_callback(msg)
        else:
            logger.debug(f"Tick received: {msg}")

    def _on_open(self, wsapp):
        logger.info("WebSocket Connection Opened")

    def _on_error(self, wsapp, error):
        logger.error(f"WebSocket Error: {error}")

    def _on_close(self, wsapp):
        logger.info("WebSocket Connection Closed")

    def subscribe(self, tokens, exchange_type=1, mode=1):
        """
        Subscribe to a list of tokens.
        :param tokens: List of instrument tokens (strings)
        :param exchange_type: 1 for NSE, 2 for NFO, etc.
        :param mode: 1 for LTP, 2 for Quote, 3 for Snap Quote
        """
        correlation_id = "trading_bot_stream"
        token_list = [{"exchangeType": exchange_type, "tokens": tokens}]
        
        # Note: sws.subscribe should be called after connection is open.
        # Often better to call it inside _on_open or after a short delay.
        threading.Timer(2, lambda: self.sws.subscribe(correlation_id, mode, token_list)).start()

    def connect(self):
        """
        Start the WebSocket connection in a separate thread.
        """
        ws_thread = threading.Thread(target=self.sws.connect)
        ws_thread.daemon = True
        ws_thread.start()
        logger.info("WebSocket thread started.")

if __name__ == "__main__":
    print("WebSocket module loaded.")
