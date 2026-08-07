from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class LifecycleStatus(str, Enum):
    DETECTED = "DETECTED"
    TRIGGERED = "TRIGGERED"
    INVALIDATED = "INVALIDATED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


@dataclass
class StrategyEvent:
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    direction: Direction
    detected_at: str
    reference_price: float
    entry_zone: List[float] = field(default_factory=list)
    invalidation: Optional[float] = None
    targets: List[float] = field(default_factory=list)
    confidence: float = 1.0
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    lifecycle_status: LifecycleStatus = LifecycleStatus.DETECTED
