from datetime import datetime
from pydantic import BaseModel, Field

class Candle(BaseModel):
    symbol: str = Field("FLOW", min_length=1, max_length=20)
    timestamp: datetime
    
    # OHLCV
    open: float
    high: float
    low: float
    close: float
    volume: int

class CandleMetrics(BaseModel):
    price_change: float
    price_change_pct: float
    volume_change: int | None
    volume_change_pct: float | None