"""
CYCLE THEORY V111 — FIDELITY PORT
CycleTheoryTelemetry — eventos auditáveis (Seção 73 do prompt-mestre).
Nenhum evento aqui modifica regra de negócio; serve só para auditoria/paridade.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class EventType(Enum):
    CYCLE_STARTED = auto()
    COUNTING_STARTED = auto()
    CHANNEL_DEFINED = auto()
    CHANNEL_INVALID = auto()
    SPLIT_ACTIVATED = auto()
    INITIAL_BREAKOUT_UP = auto()
    INITIAL_BREAKOUT_DOWN = auto()
    EXPANSION_WAIT_BUY = auto()
    EXPANSION_WAIT_SELL = auto()
    EXPANSION_CONFIRMED = auto()
    SETUP_REVERSED = auto()
    ORDER_SUBMITTED = auto()
    LIMIT_PENDING = auto()
    LIMIT_FILLED = auto()
    PULLBACK_MISSED = auto()
    POSITION_OPENED = auto()
    TARGET_LEVEL_REACHED = auto()
    PARTIAL_EXECUTED = auto()
    BREAKEVEN_APPLIED = auto()
    TRAILING_UPDATED = auto()
    POSITION_CLOSED = auto()
    DAILY_STOP = auto()
    DAILY_TARGET = auto()
    CAPITAL_TRAIL_ACTIVE = auto()
    CAPITAL_PROTECTED = auto()
    CYCLE_RESET = auto()
    PANIC = auto()
    ORDER_ERROR = auto()


@dataclass
class Event:
    type: EventType
    symbol: str
    payload: dict[str, Any]
    at: datetime = field(default_factory=datetime.utcnow)


class CycleTheoryTelemetry:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, type_: EventType, symbol: str, payload: dict[str, Any]) -> None:
        self.events.append(Event(type_, symbol, payload))

    def events_of(self, type_: EventType) -> list[Event]:
        return [e for e in self.events if e.type == type_]
