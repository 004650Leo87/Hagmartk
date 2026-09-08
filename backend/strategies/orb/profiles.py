from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import ExecutionMode, InstrumentProfile, PriceSource


DEFAULT_POLICY_PATH = Path("config/orb_session_profiles.json")
BINANCE_PROVIDER = "BINANCE_USDM_FUTURES"


@dataclass(frozen=True)
class OrbProfileResolution:
    profile: Optional[InstrumentProfile]
    profile_id: str
    profile_hash: str
    eligible: bool
    reason: str = ""


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _parse_time(value: str) -> time:
    parts = str(value).strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"INVALID_CONFIG: invalid time {value!r}")
    hour, minute = int(parts[0]), int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    return time(hour=hour, minute=minute, second=second)


def load_orb_profile_policy(path: Path = DEFAULT_POLICY_PATH) -> Dict[str, Any]:
    if not path.exists():
        raise ValueError(f"INVALID_CONFIG: ORB profile policy not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("INVALID_CONFIG: ORB profile policy must be an object")
    return payload


def _template_hash(template: Dict[str, Any]) -> str:
    encoded = json.dumps(template, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _matching_template(row: Dict[str, Any], policy: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    provider = str(row.get("provider") or "").upper()
    market = str(row.get("category") or "").upper()
    contract_type = str(row.get("contract_type") or "").upper()
    for template in policy.get("templates", []):
        if not isinstance(template, dict) or not template.get("active", True):
            continue
        if str(template.get("provider") or "").upper() != provider:
            continue
        if template.get("market") and str(template.get("market")).upper() != market:
            continue
        if template.get("contract_type") and str(template.get("contract_type")).upper() != contract_type:
            continue
        return dict(template)
    return None


def resolve_orb_profile(row: Dict[str, Any], policy: Dict[str, Any]) -> OrbProfileResolution:
    template = _matching_template(row, policy)
    if template is None:
        return OrbProfileResolution(None, "", "", False, "NO_EXPLICIT_SESSION_PROFILE")

    profile_id = str(template.get("profile_id") or "").strip()
    profile_hash = _template_hash(template)
    provider = str(row.get("provider") or "").upper()
    settle = str(row.get("settle_asset") or row.get("currency_profit") or "").upper()
    fee_rates = template.get("fee_rates") or {}
    fee_row = fee_rates.get(settle)
    if not isinstance(fee_row, dict):
        return OrbProfileResolution(None, profile_id, profile_hash, False, "UNSUPPORTED_SETTLEMENT_FEE_MODEL")

    tick_size = _d(row.get("point") or 0)
    q_min = _d(row.get("volume_min") or 0)
    q_max = _d(row.get("volume_max") or 0)
    q_step = _d(row.get("volume_step") or 0)
    point_value = _d(row.get("trade_contract_size") or 0)
    if min(tick_size, q_min, q_max, q_step, point_value) <= 0:
        return OrbProfileResolution(None, profile_id, profile_hash, False, "INVALID_INSTRUMENT_METADATA")

    if provider != BINANCE_PROVIDER:
        return OrbProfileResolution(None, profile_id, profile_hash, False, "PROVIDER_PROFILE_NOT_IMPLEMENTED")

    equity_map = template.get("paper_equity_by_settle") or {}
    paper_equity = _d(equity_map.get(settle, template.get("paper_allocated_equity", "0")))
    if paper_equity <= 0:
        return OrbProfileResolution(None, profile_id, profile_hash, False, "INVALID_PAPER_EQUITY_MODEL")

    profile = InstrumentProfile(
        instrument_id=str(row.get("instrument_id") or f"{provider}:{row.get('symbol', '')}"),
        market=str(row.get("category") or "CRYPTO"),
        provider=provider,
        contract_id=str(row.get("symbol") or ""),
        session_timezone=str(template["session_timezone"]),
        session_start_local=_parse_time(str(template["session_start_local"])),
        session_end_local=_parse_time(str(template["session_end_local"])),
        source_price=PriceSource(str(template.get("source_price") or "LAST").upper()),
        tick_size=tick_size,
        grid_origin=_d(template.get("grid_origin", "0")),
        quantity_min=q_min,
        quantity_max=q_max,
        quantity_step=q_step,
        contract_model=str(template.get("contract_model") or "LINEAR").upper(),
        point_value=point_value,
        account_currency=settle,
        allocated_equity=paper_equity,
        margin_available=paper_equity,
        margin_per_unit=Decimal("0"),
        fees_roundtrip_per_unit=Decimal("0"),
        slippage_entry_ticks=int(template["slippage_entry_ticks"]),
        slippage_stop_ticks=int(template["slippage_stop_ticks"]),
        slippage_time_ticks=int(template["slippage_time_ticks"]),
        spread_ticks=0,
        execution_mode=ExecutionMode(str(template.get("execution_mode") or "TICK_BID_ASK").upper()),
        data_resolution=str(template.get("data_resolution") or "M5_KLINE+BOOK_TICKER_SNAPSHOT"),
        trading_weekdays=tuple(int(x) for x in template.get("trading_weekdays", [0, 1, 2, 3, 4, 5, 6])),
        fee_rate_entry=_d(fee_row["taker"]),
        fee_rate_exit_stop=_d(fee_row["taker"]),
        fee_rate_exit_target=_d(fee_row["maker"]),
        fee_rate_exit_time=_d(fee_row["taker"]),
        paper_leverage=_d(template.get("paper_leverage", "1")),
        cost_model=str(template.get("cost_model") or ""),
    )
    return OrbProfileResolution(profile, profile_id, profile_hash, True, "")


def resolve_orb_universe(rows: Iterable[Dict[str, Any]], policy: Dict[str, Any]) -> Tuple[List[Tuple[Dict[str, Any], OrbProfileResolution]], Dict[str, int]]:
    resolved: List[Tuple[Dict[str, Any], OrbProfileResolution]] = []
    reasons: Dict[str, int] = {}
    for row in rows:
        result = resolve_orb_profile(dict(row), policy)
        if result.eligible:
            resolved.append((dict(row), result))
        else:
            reasons[result.reason] = reasons.get(result.reason, 0) + 1
    return resolved, reasons
