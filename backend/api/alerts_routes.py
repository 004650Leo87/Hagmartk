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
from backend.services.strategy_performance import StrategyPerformanceService

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
        alert = dashboard_alert(build_dvp_alert(event_type, event, details))
        alert["operation_id"] = str(event.event_id)
        alert["evidence"] = {
            "pivot_1_time": event.pivot_1_time,
            "pivot_1_price": event.pivot_1_price,
            "pivot_2_time": event.pivot_2_time,
            "pivot_2_price": event.pivot_2_price,
            "confluence_time": event.confluence_time,
            "pattern_type": event.pattern_type,
            "relative_volume": event.relative_volume,
            "activation_level": event.activation_level,
        }
        result.append(alert)
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
        alert = dashboard_alert(build_cycle_alert(event))
        levels = row.get("levels") or {}
        payload = row.get("payload") or {}
        entry_key = levels.get("entry") or "0"
        ticket = payload.get("ticket") or ""
        fallback_key = f"TC:{row.get('symbol')}:{row.get('timeframe')}:{ticket}:{entry_key}"
        alert["operation_id"] = str(payload.get("operation_id") or fallback_key)
        alert["evidence"] = {
            "channel_high": levels.get("channel_high"),
            "channel_low": levels.get("channel_low"),
            "expansion": levels.get("expansion"),
            "c1_mid": levels.get("c1_mid"),
            "ref_time_start": levels.get("ref_time_start"),
            "is_split_active": levels.get("is_split_active"),
            "mid_line50": levels.get("mid_line50"),
        }
        result.append(alert)
    return result

def _orb_alerts(limit: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    try:
        store = OrbShadowStore()
        rows = store.recent_events(limit)
    except Exception:
        return result
    for row in rows:
        payload = dict(row.get("payload") or {})
        payload.setdefault("symbol", row.get("symbol"))
        payload.setdefault("event_time", row.get("event_time"))
        payload.setdefault("session_id", row.get("session_id"))
        alert = dashboard_alert(build_orb_alert(str(row.get("event_type") or ""), payload))
        session = store.get_session(str(row.get("session_id") or "")) or {}
        alert["operation_id"] = str(row.get("session_id") or row.get("event_id") or "")
        alert["evidence"] = {
            "range_high": session.get("range_high"),
            "range_low": session.get("range_low"),
            "t0": session.get("t0"),
            "signal_time": session.get("signal_time"),
        }
        result.append(alert)
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


@router.get("/performance")
def get_strategy_performance() -> Dict[str, Any]:
    return StrategyPerformanceService().summary()
