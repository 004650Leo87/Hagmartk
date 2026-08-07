from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class StrategyResponse(BaseModel):
    strategy_id: str
    name: str
    version: str
    description: str
    allowed_timeframes: List[str]
    warmup_bars: int
    allow_open_candle: bool
    parameters: Dict[str, Any]
