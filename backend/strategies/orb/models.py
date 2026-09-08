from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional, Tuple


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def sign(self) -> Decimal:
        return Decimal("1") if self is Direction.LONG else Decimal("-1")


class PriceSource(str, Enum):
    LAST = "LAST"
    BID = "BID"


class ExecutionMode(str, Enum):
    TICK_BID_ASK = "TICK_BID_ASK"
    OHLC_REFERENCE = "OHLC_REFERENCE"
    LIVE_ADAPTER = "LIVE_ADAPTER"


class SessionState(str, Enum):
    WAIT_SESSION = "WAIT_SESSION"
    BUILD_RANGE = "BUILD_RANGE"
    WAIT_SIGNAL = "WAIT_SIGNAL"
    ENTRY_PENDING = "ENTRY_PENDING"
    OPEN = "OPEN"
    EXIT_PENDING = "EXIT_PENDING"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    ERROR_RECONCILE = "ERROR_RECONCILE"


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True)
class Quote:
    time: datetime
    bid: Decimal
    ask: Decimal


@dataclass(frozen=True)
class InstrumentProfile:
    instrument_id: str
    market: str
    provider: str
    contract_id: str
    session_timezone: str
    session_start_local: time
    session_end_local: time
    source_price: PriceSource
    tick_size: Decimal
    grid_origin: Decimal
    quantity_min: Decimal
    quantity_max: Decimal
    quantity_step: Decimal
    contract_model: str
    point_value: Decimal
    account_currency: str
    allocated_equity: Decimal
    margin_available: Decimal
    margin_per_unit: Decimal
    fees_roundtrip_per_unit: Decimal
    slippage_entry_ticks: int
    slippage_stop_ticks: int
    slippage_time_ticks: int
    spread_ticks: int
    execution_mode: ExecutionMode
    data_resolution: str
    trading_weekdays: Tuple[int, ...] = (0, 1, 2, 3, 4)
    holidays: Tuple[date, ...] = ()
    early_closes: Dict[date, time] = field(default_factory=dict)
    session_fold: Optional[int] = None


@dataclass(frozen=True)
class SessionWindow:
    session_id: str
    local_date: date
    t0: datetime
    session_end: datetime
    t60: datetime
    t120: datetime


@dataclass(frozen=True)
class OpeningRange:
    high: Decimal
    low: Decimal
    width: Decimal
    frozen_at: datetime


@dataclass(frozen=True)
class Signal:
    signal_id: str
    session_id: str
    direction: Direction
    candle_open_time: datetime
    candle_close_time: datetime
    close: Decimal
    t_signal: datetime


@dataclass(frozen=True)
class EntryPreflight:
    direction: Direction
    quote: Quote
    stop: Decimal
    entry_model: Decimal
    budget_cash: Decimal
    quantity: Decimal
    estimated_stop_fill: Decimal
    estimated_loss_cash: Decimal


@dataclass(frozen=True)
class TradeLevels:
    direction: Direction
    quantity: Decimal
    entry: Decimal
    stop: Decimal
    risk_price: Decimal
    target: Decimal
    rr_effective: Decimal
    risk_cash: Decimal


@dataclass(frozen=True)
class ExitDecision:
    reason: str
    price: Optional[Decimal]
    time: datetime
    unresolved: bool = False
    detail: str = ""


@dataclass(frozen=True)
class TradeRecord:
    direction: Direction
    pnl_gross: Decimal
    costs_cash: Decimal
    pnl_net: Decimal
    risk_cash: Decimal
    r_multiple: Decimal
    exit_reason: str
