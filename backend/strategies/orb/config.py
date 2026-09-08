from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import json
from typing import Tuple


@dataclass(frozen=True)
class OrbConfig:
    strategy_id: str = "ORB_OPENING_RANGE_15M_5M_2R"
    strategy_version: str = "1.0.0"
    opening_range_minutes: int = 15
    signal_timeframe_minutes: int = 5
    entry_cutoff_minutes: int = 60
    force_exit_minutes: int = 120
    breakout_buffer_ticks: int = 1
    stop_buffer_ticks: int = 1
    target_count: int = 1
    target_r_multiple: Decimal = Decimal("2")
    target_position_fraction: Decimal = Decimal("1")
    directions: str = "BOTH"
    max_signal_opportunities_per_session: int = 1
    max_entry_requests_per_session: int = 1
    max_positions_per_symbol: int = 1
    risk_fraction: Decimal = Decimal("0.0025")
    entry_quote_ttl_ms: int = 5000
    partials: bool = False
    trailing_stop: bool = False
    breakeven: bool = False
    reentry: bool = False
    reversal: bool = False
    pyramiding: bool = False
    martingale: bool = False

    def validate(self) -> None:
        if self.opening_range_minutes != 15:
            raise ValueError("INVALID_CONFIG: opening_range_minutes must remain 15 in v1")
        if self.signal_timeframe_minutes != 5:
            raise ValueError("INVALID_CONFIG: signal_timeframe_minutes must remain 5 in v1")
        if self.entry_cutoff_minutes != 60 or self.force_exit_minutes != 120:
            raise ValueError("INVALID_CONFIG: v1 timing contract changed")
        if self.breakout_buffer_ticks != 1 or self.stop_buffer_ticks != 1:
            raise ValueError("INVALID_CONFIG: v1 tick buffers changed")
        if self.target_count != 1 or self.target_r_multiple != Decimal("2"):
            raise ValueError("INVALID_CONFIG: v1 target contract changed")
        if self.target_position_fraction != Decimal("1"):
            raise ValueError("INVALID_CONFIG: v1 target must close 100%")
        if self.risk_fraction != Decimal("0.0025"):
            raise ValueError("INVALID_CONFIG: v1 risk fraction changed")
        if self.entry_quote_ttl_ms != 5000:
            raise ValueError("INVALID_CONFIG: v1 entry TTL changed")
        if any((self.partials, self.trailing_stop, self.breakeven, self.reentry,
                self.reversal, self.pyramiding, self.martingale)):
            raise ValueError("INVALID_CONFIG: prohibited v1 behavior enabled")

    def canonical_payload(self) -> dict:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = format(value, "f")
        return payload

    def config_hash(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


DEFAULT_ORB_CONFIG = OrbConfig()
DEFAULT_ORB_CONFIG.validate()
ORB_V1_CONFIG_HASH = DEFAULT_ORB_CONFIG.config_hash()

ORB_V1_FORBIDDEN_FEATURES: Tuple[str, ...] = (
    "STRATEGIC_PARTIALS", "TRAILING_STOP", "BREAKEVEN", "REENTRY",
    "REVERSAL", "PYRAMIDING", "MARTINGALE", "POSITION_INCREASE",
)
