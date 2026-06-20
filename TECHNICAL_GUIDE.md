# Technical Documentation & Module Guide

## 1. Authentication & API (`app/angel_api.py`)
Uses the `SmartConnect` SDK. Authentication requires an API Key and TOTP. The `AngelOneClient` class handles session management and token refreshes.

## 2. Market Structure Engine (`app/smc.py`)
The heart of the bot's SMC logic.
- **`find_swings`**: Uses a rolling window to find relative highs and lows.
- **`detect_structure`**: Identifies BOS (Break of Structure) when price breaks a swing point in the direction of the trend, and CHoCH (Change of Character) for potential reversals.
- **`detect_fvg`**: Scans for 3-candle imbalances.
- **`detect_liquidity_sweep`**: Monitors if price has taken out previous swing liquidity.

## 3. Data Flow (`app/main.py`)
- **Ticks**: Received via `websocket.py`.
- **Aggregation**: Ticks are grouped into 1-minute OHLC candles.
- **Storage**: 1m candles are immediately sent to `database.py` (PostgreSQL).
- **Higher Timeframes**: 5m and 15m candles are built from 1m data to ensure consistency.

## 4. Database Schema
### Table: `candles`
- `symbol`, `timeframe`, `timestamp`, `open`, `high`, `low`, `close`, `volume`.
- Unique Constraint: `(symbol, timeframe, timestamp)`.

### Table: `trades`
- `symbol`, `side`, `entry_price`, `exit_price`, `quantity`, `sl_price`, `tp_price`, `status`.

## 5. Dashboard Configuration
The dashboard uses FastAPI with Jinja2 templates.
- **Template**: `app/templates/index.html`.
- **Styles**: Bootstrap 5 for responsiveness.
- **Data Injection**: The `set_bot_instance` helper allows routes to access the live memory buffers of the running bot.

## 6. Backtesting Methodology (`app/backtest.py`)
- **Event-Driven**: The engine processes data candle-by-candle.
- **Memory Efficient**: It doesn't load all data at once but slices it for the strategy to mimic real-time constraints.
- **Slippage & Costs**: Current version assumes zero slippage and commissions (can be added in `_close_trade`).
