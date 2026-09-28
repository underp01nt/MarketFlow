from datetime import datetime
from pydantic import BaseModel, Field

class Candle(BaseModel):
    symbol: str
    timestamp: datetime
    
    # OHLCV
    open: float
    high: float
    low: float
    close: float
    volume: int = Field(ge=0)