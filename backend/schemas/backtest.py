from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str
    bars: int = Field(default=500, ge=10, le=10000)
    offset: int = Field(default=0, ge=0)
    intrabar_policy: str = "CONSERVATIVE"
    spread_points: float = 0.0
    commission_per_trade: float = 0.0
    slippage_points: float = 0.0
    in_sample_ratio: float = 0.70
    version: Optional[str] = None
