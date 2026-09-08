from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query

from backend.domain.shadow_models import ShadowEventType
from backend.services.cycle_theory_shadow_store import CycleTheoryShadowStore
from backend.services.market_alert_template import (
    build_cycle_alert,
    build_dvp_alert,
    build_orb_alert,
    dashboard_alert,
)
from backend.services.orb_shadow_store import OrbShadowStore
from backend.services.shadow_store import ShadowStoreRepository

router = APIRouter(prefix="/api/alerts", tags=["Market Alerts"])

_DVP_STATE_EVENT = {
    "ARMED": ShadowEventType.SETUP_ARMED,
    "ACTIVATED": ShadowEventType.ENTRY_ACTIVATED,
    "TARGET_2R": ShadowEventType.TARGET_REACHED,
    "STOPPED": ShadowEventType.STOP_REACHED,
    "EXPIRED": ShadowEventType.SETUP_EXPIRED,
    "INVALIDATED": ShadowEventType.SETUP_INVALIDATED,
}

def _dvp_alerts(limit: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    try:
        events = ShadowStoreRepository().list_history_events()[: max(limit * 2, 20)]
    except Exception:
        return result
    for event in events:
        event_type = _DVP_STATE_EVENT.get(str(event.current_state))
        if event_type is None:
            continue
        details = {
            "candle_timestamp": event.market_candle_time or event.updated_at or event.created_at,
            "reason": str(event.current_state),
        }
        result.append(dashboard_alert(build_dvp_alert(event_type, event, details)))
        if len(result) >= limit:
            break
    return result


def _cycle_alerts(limit: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    try:
        rows = CycleTheoryShadowStore().recent_events(limit)
    except Exception:
        return result
    allowed = {
        "EXPANSION_CONFIRMED", "ORDER_SUBMITTED", "LIMIT_FILLED", "POSITION_OPENED",
        "PARTIAL_EXECUTED", "BREAKEVEN_APPLIED", "TARGET_LEVEL_REACHED",
        "TAKE_PROFIT", "STOP_LOSS", "POSITION_CLOSED", "PULLBACK_MISSED",
    }
    for row in rows:
        if str(row.get("event_type") or "") not in allowed:
            continue
        event = dict(row)
        event["payload"] = row.get("payload") or {}
        event["levels"] = row.get("levels") or {}
        result.append(dashboard_alert(build_cycle_alert(event)))
    return result

def _orb_alerts(limit: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    try:
        rows = OrbShadowStore().recent_events(limit)
    except Exception:
        return result
    for row in rows:
        payload = dict(row.get("payload") or {})
        payload.setdefault("symbol", row.get("symbol"))
        payload.setdefault("event_time", row.get("event_time"))
        payload.setdefault("session_id", row.get("session_id"))
        result.append(dashboard_alert(build_orb_alert(str(row.get("event_type") or ""), payload)))
    return result


@router.get("/recent")
def get_recent_market_alerts(
    limit: int = Query(30, ge=1, le=100),
    strategy: str = Query("ALL"),
) -> Dict[str, Any]:
    selected = strategy.upper().strip()
    rows: List[Dict[str, Any]] = []
    if selected in {"ALL", "DVP"}:
        rows.extend(_dvp_alerts(limit))
    if selected in {"ALL", "TC", "CYCLE"}:
        rows.extend(_cycle_alerts(limit))
    if selected in {"ALL", "ORB"}:
        rows.extend(_orb_alerts(limit))
    rows.sort(key=lambda item: item.get("event_time_utc") or "", reverse=True)
    rows = rows[:limit]
    return {
        "count": len(rows),
        "alerts": rows,
        "timezone": "America/Sao_Paulo",
        "paper_only": True,
        "real_order_execution_enabled": False,
    }
