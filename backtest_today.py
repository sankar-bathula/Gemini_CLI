import pandas as pd
from app.angel_api import AngelOneClient
from app.data_collector import DataCollector
from app.backtest import BacktestEngine
from logzero import logger
from datetime import datetime

def run_today_backtest():
    # 1. Setup
    client = AngelOneClient()
    if not client.login():
        logger.error("Failed to login for backtest.")
        return

    collector = DataCollector(client)
    
    # Define timeframe: Fetch 5 days to prime indicators, but we'll focus on today
    now = datetime.now()
    to_date = now.strftime("%Y-%m-%d %H:%M")
    from_date = (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
    today_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    
    # NIFTY Index details
    symbol = "Nifty 50"
    token = "99926000"
    exchange = "NSE"
    
    logger.info(f"Fetching data for {symbol} to analyze today's trades...")

    # 2. Fetch Data
    df_15m = collector.get_historical_candles(exchange, symbol, token, "FIFTEEN_MINUTE", from_date, to_date)
    df_5m = collector.get_historical_candles(exchange, symbol, token, "FIVE_MINUTE", from_date, to_date)
    df_1m = collector.get_historical_candles(exchange, symbol, token, "ONE_MINUTE", from_date, to_date)

    if df_15m is None or df_15m.empty or df_5m is None or df_5m.empty or df_1m is None or df_1m.empty:
        logger.error("Could not fetch required historical data.")
        return

    # Process and align data
    for df in [df_15m, df_5m, df_1m]:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

    # 3. Run Engine
    engine = BacktestEngine(initial_balance=100000)
    engine.run(df_15m, df_5m, df_1m)

    # 4. Filter and Display Today's Trades
    today_trades = [t for t in engine.trades if t['entry_time'] >= today_start]
    
    print("\n" + "="*40)
    print(f" TODAY'S TRADES ({now.strftime('%Y-%m-%d')}) ")
    print("="*40)
    if not today_trades:
        print("No trades triggered today based on the strategy.")
    else:
        df_today = pd.DataFrame(today_trades)
        for _, trade in df_today.iterrows():
            print(f"Time: {trade['entry_time']} | Side: {trade['side']} | Entry: {trade['entry_price']} | Exit: {trade['exit_price']} | PnL: {trade['pnl']:.2f} ({trade['reason']})")
        
        print("-"*40)
        print(f"Today's Total PnL: {df_today['pnl'].sum():.2f}")
        print(f"Today's Win Rate: {(df_today['pnl'] > 0).mean()*100:.1f}%")
    print("="*40 + "\n")

if __name__ == "__main__":
    from datetime import timedelta
    run_today_backtest()
