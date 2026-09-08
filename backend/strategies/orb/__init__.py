"""ORB Opening Range 15M/5M/2R v1.0.0 deterministic research core."""

from .config import DEFAULT_ORB_CONFIG, ORB_V1_CONFIG_HASH, OrbConfig
from .core import (
    build_opening_range,
    evaluate_signal,
    finalize_trade_levels,
    first_signal,
    fixed_stop,
    resolve_session_window,
    size_linear_entry,
    validate_entry_quote,
    validate_profile,
)

__all__ = [
    "DEFAULT_ORB_CONFIG", "ORB_V1_CONFIG_HASH", "OrbConfig",
    "build_opening_range", "evaluate_signal", "finalize_trade_levels",
    "first_signal", "fixed_stop", "resolve_session_window", "size_linear_entry",
    "validate_entry_quote", "validate_profile",
]
