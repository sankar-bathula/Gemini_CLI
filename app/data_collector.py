import pandas as pd
from logzero import logger
from app.instruments import InstrumentManager

class DataCollector:
    def __init__(self, client):
        self.client = client
        self.im = InstrumentManager()
        self.im.fetch_instruments()

    def get_nifty_spot(self):
        """
        Fetches NIFTY Spot LTP.
        Token for NIFTY Index is 99926000.
        """
        try:
            data = self.client.smart_api.ltpData(
"NSE", "Nifty 50", "99926000")
            if data['status']:
                return data['data']['ltp']
        except Exception as e:
            logger.error(f"Error fetching NIFTY Spot: {e}")
        return None

    def get_nifty_futures(self):
        """
        Fetches NIFTY near-month Futures LTP.
        """
        fut_instrument = self.im.get_nifty_futures()
        if not fut_instrument:
            return None
        
        try:
            data = self.client.smart_api.ltpData(
"NFO", fut_instrument['symbol'], fut_instrument['token'])
            if data['status']:
                return data['data']['ltp']
        except Exception as e:
            logger.error(f"Error fetching NIFTY Futures: {e}")
        return None

    def get_historical_candles(self, exchange, symbol, token, interval, from_date, to_date):
        """
        Fetches historical candle data.
        Intervals: ONE_MINUTE, FIVE_MINUTE, TEN_MINUTE, FIFTEEN_MINUTE, THIRTY_MINUTE, ONE_HOUR, ONE_DAY
        """
        params = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": interval,
            "fromdate": from_date,
            "todate": to_date
        }
        try:
            data = self.client.smart_api.getCandleData(params)
            if data['status']:
                df = pd.DataFrame(data['data'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                return df
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
        return None

    def find_strike_by_premium(self, option_type, target_premium=250):
        """
        Finds the NIFTY option strike closest to the target premium for the nearest weekly expiry.
        """
        expiry = self.im.get_weekly_expiry()
        if not expiry:
            return None
            
        spot = self.get_nifty_spot()
        if not spot:
            return None
            
        # Get all options for this expiry and type
        options = self.im.df[
            (self.im.df['name'] == 'NIFTY') & 
            (self.im.df['exch_seg'] == 'NFO') & 
            (self.im.df['expiry'] == expiry) &
            (self.im.df['symbol'].str.endswith(option_type.upper()))
        ].copy()
        
        # Convert strike to numeric for filtering
        options['strike_val'] = pd.to_numeric(options['strike']) / 100
        
        # Narrow down strikes near the spot to reduce API calls
        # Typically, a premium of 250 is found within +/- 1000 points of spot
        options = options[abs(options['strike_val'] - spot) <= 1000]
        
        tokens = options['token'].tolist()
        best_match = None
        min_diff = float('inf')
        
        # Batch fetch LTP for efficiency
        batch_size = 50
        for i in range(0, len(tokens), batch_size):
            batch = tokens[i:i+batch_size]
            try:
                # Using getMarketData for batch LTP
                data = self.client.smart_api.getMarketData("LTP", {"NFO": batch})
                if data['status'] and 'fetched' in data['data']:
                    for item in data['data']['fetched']:
                        ltp = float(item['ltp'])
                        diff = abs(ltp - target_premium)
                        if diff < min_diff:
                            min_diff = diff
                            match_row = options[options['token'] == item['symbolToken']].iloc[0]
                            best_match = match_row.to_dict()
                            best_match['ltp'] = ltp
            except Exception as e:
                logger.error(f"Error fetching batch LTP: {e}")
                
        return best_match

if __name__ == "__main__":
    print("Data Collector module loaded.")
