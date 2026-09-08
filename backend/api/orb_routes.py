from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Request

from backend.strategies.orb.config import DEFAULT_ORB_CONFIG, ORB_V1_CONFIG_HASH
from backend.services.orb_shadow_store import OrbShadowStore

router = APIRouter(prefix="/api/orb", tags=["ORB"])

_PROFILE_PATH = Path(os.environ.get(
    "HAGMARTK_ORB_SESSION_PROFILES",
    "config/orb_session_profiles.json",
))


def _load_profiles() -> List[Dict[str, Any]]:
    if not _PROFILE_PATH.exists():
        return []
    payload = json.loads(_PROFILE_PATH.read_text(encoding="utf-8-sig"))
    rows = payload.get("profiles", []) if isinstance(payload, dict) else []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _profile_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    allowed = (
        "instrument_id", "market", "provider", "contract_id",
        "session_timezone", "session_start_local", "session_end_local",
        "source_price", "execution_mode", "data_resolution", "active",
    )
    return {key: row.get(key) for key in allowed if key in row}


@router.get("/status")
def get_orb_status(request: Request) -> Dict[str, Any]:
    system = getattr(request.app.state, "system", None) or {}
    scanner = system.get("orb_scanner") if isinstance(system, dict) else None
    if scanner is not None and hasattr(scanner, "status"):
        return scanner.status()
    profiles = _load_profiles()
    active = [row for row in profiles if row.get("active", True)]
    blocked = len(active) == 0
    return {
        "strategy_id": DEFAULT_ORB_CONFIG.strategy_id,
        "version": DEFAULT_ORB_CONFIG.strategy_version,
        "display_name": "ORB",
        "stage": "SHADOW",
        "config_hash": ORB_V1_CONFIG_HASH,
        "engine_core_ready": True,
        "conformance_suite": "tests/strategies/test_orb_v1_core.py",
        "session_profiles_configured": len(active),
        "prospective_shadow_enabled": False,
        "blocking_reason": (
            "EXPLICIT_SESSION_PROFILES_REQUIRED" if blocked
            else "PROSPECTIVE_SHADOW_NOT_PROMOTED"
        ),
        "paper_only": True,
        "real_order_execution_enabled": False,
        "tradingview_indicator": "ORB",
    }


@router.get("/config")
def get_orb_config() -> Dict[str, Any]:
    return {
        "strategy_id": DEFAULT_ORB_CONFIG.strategy_id,
        "version": DEFAULT_ORB_CONFIG.strategy_version,
        "config_hash": ORB_V1_CONFIG_HASH,
        "parameters": DEFAULT_ORB_CONFIG.canonical_payload(),
        "real_order_execution_enabled": False,
    }


@router.get("/session-profiles")
def get_orb_session_profiles() -> Dict[str, Any]:
    rows = [_profile_summary(row) for row in _load_profiles()]
    return {
        "count": len(rows),
        "profiles": rows,
        "policy": "EXPLICIT_ONLY_NO_UNIVERSAL_OPEN_ASSUMPTION",
    }


@router.get("/tradingview")
def get_orb_tradingview() -> Dict[str, Any]:
    return {
        "name": "ORB",
        "script_path": "integrations/tradingview/ORB_v1_indicator.pine",
        "role": "SIGNAL_CONFORMANCE_VISUALIZATION",
        "canonical_execution_ledger": "HAGMARTK",
        "real_order_execution_enabled": False,
    }


@router.get("/shadow/events")
def get_orb_shadow_events(limit: int = 100) -> Dict[str, Any]:
    store = OrbShadowStore()
    rows = store.recent_events(limit=limit)
    return {"count": len(rows), "events": rows, "paper_only": True, "real_order_execution_enabled": False}


@router.get("/shadow/statistics")
def get_orb_shadow_statistics() -> Dict[str, Any]:
    store = OrbShadowStore()
    return store.statistics()
