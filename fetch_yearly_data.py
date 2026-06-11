import pandas as pd
from app.angel_api import AngelOneClient
from app.data_collector import DataCollector
from datetime import datetime, timedelta
import time
from logzero import logger
import os

def fetch_yearly_data(symbol="Nifty 50", token="99926000", interval="FIVE_MINUTE"):
    client = AngelOneClient()
    if not client.login():
        return

    collector = DataCollector(client)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    all_data = []
    
    # Fetch in 30-day chunks to avoid API limits and timeouts
    current_end = end_date
    while current_end > start_date:
        current_start = max(current_end - timedelta(days=30), start_date)
        
        from_str = current_start.strftime("%Y-%m-%d 09:15")
        to_str = current_end.strftime("%Y-%m-%d 15:30")
        
        logger.info(f"Fetching {interval} data from {from_str} to {to_str}...")
        
        df = collector.get_historical_candles("NSE", symbol, token, interval, from_str, to_str)
        
        if df is not None and not df.empty:
            all_data.append(df)
        
        current_end = current_start
        time.sleep(1) # Rate limiting
    
    if all_data:
        full_df = pd.concat(all_data).drop_duplicates().sort_values('timestamp')
        filename = f"nifty_50_1year_{interval.lower()}.csv"
        full_df.to_csv(filename, index=False)
        logger.info(f"Saved {len(full_df)} rows to {filename}")
        return full_df
    else:
        logger.error("No data fetched.")
        return None

if __name__ == "__main__":
    fetch_yearly_data()
