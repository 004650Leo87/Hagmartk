from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class OrbLedgerEvent:
    event_id: str
    strategy_id: str
    version: str
    config_hash: str
    session_id: str
    instrument_id: str
    event_type: str
    event_time: datetime
    payload: Dict[str, Any]

    def to_dict(self) -> dict:
        def normalize(value):
            if isinstance(value, Decimal):
                return format(value, "f")
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, dict):
                return {str(k): normalize(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [normalize(v) for v in value]
            return value
        return normalize(asdict(self))


def deterministic_event_id(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class OrbLedger:
    """Append-only in-memory canonical ledger; storage adapters persist these rows."""

    def __init__(self) -> None:
        self._events: List[OrbLedgerEvent] = []
        self._ids: set[str] = set()

    def append(self, event: OrbLedgerEvent) -> bool:
        if event.event_id in self._ids:
            return False
        self._ids.add(event.event_id)
        self._events.append(event)
        return True

    def events(self) -> tuple[OrbLedgerEvent, ...]:
        return tuple(self._events)

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e.to_dict(), sort_keys=True, separators=(",", ":")) for e in self._events)
