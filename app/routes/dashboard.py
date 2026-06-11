from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import pandas as pd

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    if not bot_instance:
        return "Bot not initialized"
    
    # 1. Get Strategy Info
    trend_bias = "NEUTRAL"
    setup = {"sweep": 0, "fvg": 0}
    
    if not bot_instance.buffer_15m.empty:
        # Use existing TrendAnalyzer to get fresh bias
        from app.trend import TrendAnalyzer
        analyzer = TrendAnalyzer(bot_instance.buffer_15m)
        analyzer.calculate_indicators()
        trend_bias = analyzer.get_market_direction()

    if not bot_instance.buffer_5m.empty:
        last_5m = bot_instance.buffer_5m.iloc[-1]
        setup = {
            "sweep": last_5m.get('sweep', 0),
            "fvg": last_5m.get('fvg', 0)
        }

    # 2. Get Trades from DB
    trades = []
    if bot_instance.db and bot_instance.db.connection_pool:
        try:
            conn = bot_instance.db.connection_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM trades ORDER BY entry_time DESC LIMIT 10")
                    columns = [desc[0] for desc in cur.description]
                    trades = [dict(zip(columns, row)) for row in cur.fetchall()]
            finally:
                bot_instance.db.connection_pool.putconn(conn)
        except Exception as e:
            from logzero import logger
            logger.error(f"Error fetching trades for dashboard: {e}")
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "symbol": bot_instance.trading_symbol,
            "trend_bias": trend_bias,
            "setup": setup,
            "trades": trades,
            "last_update": datetime.now().strftime("%H:%M:%S")
        }
    )

# (Keep raw API routes for programmatic access)
@router.get("/api/status")
async def get_status():
    # ... (existing API logic)
    pass
