import requests
import pandas as pd
import json
import os
from logzero import logger

class InstrumentManager:
    URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    CACHE_FILE = "instruments.json"

    def __init__(self):
        self.df = None

    def fetch_instruments(self, force_download=False):
        """
        Fetches the instrument list from Angel One and caches it locally.
        """
        if not force_download and os.path.exists(self.CACHE_FILE):
            logger.info("Loading instruments from cache...")
            with open(self.CACHE_FILE, 'r') as f:
                data = json.load(f)
            self.df = pd.DataFrame(data)
            return self.df

        logger.info("Downloading instruments from Angel One...")
        try:
            response = requests.get(self.URL)
            response.raise_for_status()
            data = response.json()
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(data, f)
            self.df = pd.DataFrame(data)
            return self.df
        except Exception as e:
            logger.error(f"Failed to fetch instruments: {str(e)}")
            return None

    def get_token(self, symbol, exchange="NSE"):
        if self.df is None:
            self.fetch_instruments()
        
        filtered = self.df[(self.df['symbol'] == symbol) & (self.df['exch_seg'] == exchange)]
        if not filtered.empty:
            return filtered.iloc[0]['token']
        return None

    def get_nifty_futures(self):
        """
        Returns the near-month NIFTY Futures instrument.
        """
        if self.df is None:
            self.fetch_instruments()
        
        # Filter for NIFTY Futures
        futs = self.df[
            (self.df['name'] == 'NIFTY') & 
            (self.df['exch_seg'] == 'NFO') & 
            (self.df['instrumenttype'] == 'FUTIDX')
        ].copy()
        
        # Sort by expiry to get the near-month (simplistic approach)
        futs['expiry_dt'] = pd.to_datetime(futs['expiry'])
        futs = futs.sort_values(by='expiry_dt')
        
        if not futs.empty:
            return futs.iloc[0].to_dict()
        return None

    def get_weekly_expiry(self):
        """
        Returns the nearest weekly expiry date for NIFTY.
        """
        if self.df is None:
            self.fetch_instruments()
        
        nifty_options = self.df[
            (self.df['name'] == 'NIFTY') & 
            (self.df['exch_seg'] == 'NFO') & 
            (self.df['instrumenttype'] == 'OPTIDX')
        ].copy()
        
        nifty_options['expiry_dt'] = pd.to_datetime(nifty_options['expiry'])
        expiry_dates = sorted(nifty_options['expiry_dt'].unique())
        
        if expiry_dates:
            return expiry_dates[0].strftime("%d%b%Y").upper()
        return None

if __name__ == "__main__":
    im = InstrumentManager()
    im.fetch_instruments()
    print("NIFTY Futures Near Month:")
    print(im.get_nifty_futures())
