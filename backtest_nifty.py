import pandas as pd
from app.angel_api import AngelOneClient
from app.data_collector import DataCollector
from app.backtest import BacktestEngine
from logzero import logger
from datetime import datetime, timedelta

def run_nifty_backtest(days=360):
    # 1. Setup
    client = AngelOneClient()
    if not client.login():
        logger.error("Failed to login for backtest.")
        return

    collector = DataCollector(client)
    
    # Define timeframe
    # Angel One API format: "YYYY-MM-DD HH:MM"
    to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    
    # NIFTY Index details
    symbol = "Nifty 50"
    token = "99926000"
    exchange = "NSE"
    
    logger.info(f"Fetching historical data for {symbol} ({days} days)...")

    # 2. Fetch Data (15m, 5m, 1m)
    # Note: Strategy uses these three timeframes for multi-timeframe analysis
    df_15m = collector.get_historical_candles(exchange, symbol, token, "FIFTEEN_MINUTE", from_date, to_date)
    df_5m = collector.get_historical_candles(exchange, symbol, token, "FIVE_MINUTE", from_date, to_date)
    df_1m = collector.get_historical_candles(exchange, symbol, token, "ONE_MINUTE", from_date, to_date)

    if df_15m is None or df_15m.empty:
        logger.error("Could not fetch 15m data.")
        return
    if df_5m is None or df_5m.empty:
        logger.error("Could not fetch 5m data.")
        return
    if df_1m is None or df_1m.empty:
        logger.error("Could not fetch 1m data.")
        return

    # Process and align data
    for df in [df_15m, df_5m, df_1m]:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        # Ensure numeric columns
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

    logger.info(f"Data fetched successfully. 1m rows: {len(df_1m)}")

    # 3. Run Backtest Engine
    # initial_balance is in virtual currency (points or rupees)
    engine = BacktestEngine(initial_balance=100000)
    engine.run(df_15m, df_5m, df_1m)

if __name__ == "__main__":
    # You can change the number of days here
    run_nifty_backtest(days=15)
