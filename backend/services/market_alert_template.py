from __future__ import annotations

from datetime import datetime, timezone
import html
from typing import Any, Dict, Iterable, Optional
from zoneinfo import ZoneInfo

from backend.domain.shadow_models import ShadowEvent, ShadowEventType

_BR_TZ = ZoneInfo("America/Sao_Paulo")

_STRATEGY_NAMES = {
    "DVP": "HAGMARTK DVP",
    "TC": "HAGMARTK TEORIA DOS CICLOS",
    "ORB": "HAGMARTK ORB",
}

_EVENT_LABELS = {
    "WATCH": ("👀", "OPORTUNIDADE EM OBSERVAÇÃO"),
    "SIGNAL": ("⚡", "OPORTUNIDADE IDENTIFICADA"),
    "ENTRY": ("🟢", "OPERAÇÃO REGISTRADA"),
    "MILESTONE": ("✅", "MARCO ATINGIDO"),
    "TARGET": ("🎯", "ALVO ATINGIDO"),
    "STOP": ("🛑", "STOP ATINGIDO"),
    "PARTIAL": ("💰", "PARCIAL REALIZADA"),
    "BREAKEVEN": ("🛡️", "PROTEÇÃO NO ZERO ATIVADA"),
    "CLOSED": ("🏁", "OPERAÇÃO ENCERRADA"),
    "EXPIRED": ("⌛", "OPORTUNIDADE ENCERRADA"),
    "UNRESOLVED": ("⚠️", "RESULTADO PENDENTE DE CONFIRMAÇÃO"),
}

def _parse_time(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    elif value:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def brazil_time(value: Any) -> str:
    dt = _parse_time(value)
    if dt is None:
        return "—"
    local = dt.astimezone(_BR_TZ)
    return local.strftime("%d/%m/%Y • %H:%M:%S")


def _fmt_price(value: Any) -> Optional[str]:
    if value in (None, "", "—"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number <= 0:
        return None
    absolute = abs(number)
    if absolute >= 10000:
        places = 2
    elif absolute >= 100:
        places = 3
    elif absolute >= 1:
        places = 5
    elif absolute >= 0.01:
        places = 6
    else:
        places = 8
    return f"{number:.{places}f}".rstrip("0").rstrip(".")


def _direction(value: Any) -> tuple[str, str]:
    raw = str(value or "").upper()
    if raw in {"BULLISH", "BUY", "LONG", "COMPRA"}:
        return "🟢", "COMPRA"
    if raw in {"BEARISH", "SELL", "SHORT", "VENDA"}:
        return "🔴", "VENDA"
    return "⚪", "—"


def _alert(
    strategy: str,
    event_kind: str,
    symbol: Any,
    event_time: Any,
    timeframe: Any = None,
    direction: Any = None,
    entry: Any = None,
    stop: Any = None,
    targets: Optional[Iterable[tuple[str, Any]]] = None,
    result: Any = None,
    note: Any = None,
    event_code: str = "",
) -> Dict[str, Any]:
    icon, label = _EVENT_LABELS.get(event_kind, ("📌", event_kind.replace("_", " ")))
    dir_icon, dir_label = _direction(direction)
    clean_targets = []
    for target_label, target_value in targets or []:
        value = _fmt_price(target_value)
        if value:
            clean_targets.append({"label": target_label, "value": value})
    return {
        "strategy_key": strategy,
        "strategy_name": _STRATEGY_NAMES[strategy],
        "event_kind": event_kind,
        "event_code": event_code,
        "event_icon": icon,
        "event_label": label,
        "symbol": str(symbol or "—"),
        "timeframe": str(timeframe or "—"),
        "direction_icon": dir_icon,
        "direction_label": dir_label,
        "event_time_utc": _parse_time(event_time).isoformat() if _parse_time(event_time) else None,
        "event_time_brazil": brazil_time(event_time),
        "entry": _fmt_price(entry),
        "stop": _fmt_price(stop),
        "targets": clean_targets,
        "result": None if result in (None, "") else str(result),
        "note": None if note in (None, "") else str(note),
        "mode": "SHADOW / PAPER",
        "real_order_execution_enabled": False,
    }

def build_dvp_alert(event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> Dict[str, Any]:
    kinds = {
        ShadowEventType.SETUP_ARMED: "WATCH",
        ShadowEventType.ENTRY_ACTIVATED: "ENTRY",
        ShadowEventType.MILESTONE_1R: "MILESTONE",
        ShadowEventType.TARGET_REACHED: "TARGET",
        ShadowEventType.STOP_REACHED: "STOP",
        ShadowEventType.SETUP_EXPIRED: "EXPIRED",
        ShadowEventType.SETUP_INVALIDATED: "EXPIRED",
    }
    event_time = (
        details.get("candle_timestamp") or event.market_candle_time or event.activated_at
        or event.confluence_time or event.updated_at or event.created_at
    )
    result = None
    if event_type == ShadowEventType.MILESTONE_1R:
        result = f"+{float(event.mfe_r_live or 0):.2f}R"
    elif event_type == ShadowEventType.TARGET_REACHED:
        result = "+2.00R"
    elif event_type == ShadowEventType.STOP_REACHED:
        result = "-1.00R"
    note = None
    if event_type in {ShadowEventType.SETUP_EXPIRED, ShadowEventType.SETUP_INVALIDATED}:
        note = details.get("reason") or "Oportunidade encerrada sem entrada válida."
    return _alert(
        "DVP", kinds[event_type], event.symbol, event_time,
        event.timeframe, event.direction, event.entry_price or event.activation_level,
        event.initial_stop, [("Alvo 2R", event.target_2R)], result, note, event_type.value,
    )

def build_cycle_alert(event: Dict[str, Any]) -> Dict[str, Any]:
    event_type = str(event.get("event_type") or "CYCLE_EVENT")
    kinds = {
        "EXPANSION_CONFIRMED": "SIGNAL",
        "ORDER_SUBMITTED": "WATCH",
        "LIMIT_FILLED": "ENTRY",
        "POSITION_OPENED": "ENTRY",
        "PARTIAL_EXECUTED": "PARTIAL",
        "BREAKEVEN_APPLIED": "BREAKEVEN",
        "TARGET_LEVEL_REACHED": "TARGET",
        "TAKE_PROFIT": "TARGET",
        "STOP_LOSS": "STOP",
        "POSITION_CLOSED": "CLOSED",
        "PULLBACK_MISSED": "EXPIRED",
    }
    levels = event.get("levels") or {}
    payload = event.get("payload") or {}
    result = payload.get("r_multiple") or payload.get("result_r")
    note = payload.get("detail") or payload.get("reason")
    return _alert(
        "TC", kinds.get(event_type, "WATCH"), event.get("symbol"), event.get("event_time"),
        event.get("timeframe"), event.get("direction"), levels.get("entry"), levels.get("stop"),
        [("Alvo 1", levels.get("target_1")), ("Alvo 2", levels.get("target_2")),
         ("Alvo 3", levels.get("target_3"))], result, note, event_type,
    )

def build_orb_alert(event_type: str, event: Dict[str, Any]) -> Dict[str, Any]:
    kinds = {
        "SIGNAL": "SIGNAL",
        "ENTRY_FILLED": "ENTRY",
        "ENTRY_REJECTED": "EXPIRED",
        "EXIT_FILLED": "CLOSED",
        "EXIT_UNRESOLVED": "UNRESOLVED",
    }
    exit_reason = str(event.get("exit_reason") or "").upper()
    event_kind = kinds.get(event_type, "WATCH")
    if event_type == "EXIT_FILLED" and exit_reason == "TARGET":
        event_kind = "TARGET"
    elif event_type == "EXIT_FILLED" and exit_reason == "STOP":
        event_kind = "STOP"
    result = event.get("r_multiple")
    if result not in (None, ""):
        try:
            result = f"{float(result):+.2f}R"
        except Exception:
            result = str(result)
    event_time = event.get("event_time") or event.get("t_signal") or event.get("signal_time") or event.get("entry_time")
    return _alert(
        "ORB", event_kind, event.get("symbol"), event_time, "M5", event.get("direction"),
        event.get("entry") or event.get("entry_price"), event.get("stop") or event.get("stop_price"),
        [("Alvo 2R", event.get("target") or event.get("target_price"))],
        result, event.get("reason"), event_type,
    )


def format_telegram_alert(alert: Dict[str, Any]) -> str:
    lines = [
        f"{alert['event_icon']} <b>{alert['strategy_name']}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"<b>{alert['event_label']}</b>",
        "",
        f"📌 <b>Ativo:</b> {alert['symbol']}",
        f"🕒 <b>Horário (Brasília):</b> {alert['event_time_brazil']}",
        f"{alert['direction_icon']} <b>Direção:</b> {alert['direction_label']}",
    ]
    if alert.get("timeframe") and alert["timeframe"] != "—":
        lines.append(f"⏱️ <b>Gráfico:</b> {alert['timeframe']}")
    if alert.get("entry") or alert.get("stop") or alert.get("targets"):
        lines.extend(["", "🎯 <b>Níveis da operação</b>"])
        if alert.get("entry"):
            lines.append(f"Entrada: <code>{alert['entry']}</code>")
        if alert.get("stop"):
            lines.append(f"🛑 Stop: <code>{alert['stop']}</code>")
        for target in alert.get("targets") or []:
            lines.append(f"🎯 {target['label']}: <code>{target['value']}</code>")
    if alert.get("result"):
        lines.extend(["", f"📊 <b>Resultado:</b> {alert['result']}"])
    if alert.get("note"):
        lines.append(f"ℹ️ {alert['note']}")
    lines.extend([
        "",
        "🧪 <b>Acompanhamento:</b> Shadow / Simulação",
        "🔒 Nenhuma ordem real foi enviada.",
    ])
    return "\n".join(lines)


def dashboard_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "strategy": alert["strategy_name"],
        "strategy_key": alert["strategy_key"],
        "event_code": alert["event_code"],
        "event_label": alert["event_label"],
        "event_icon": alert["event_icon"],
        "symbol": alert["symbol"],
        "timeframe": alert["timeframe"],
        "direction": alert["direction_label"],
        "direction_icon": alert["direction_icon"],
        "time_brazil": alert["event_time_brazil"],
        "event_time_utc": alert["event_time_utc"],
        "entry": alert["entry"],
        "stop": alert["stop"],
        "targets": alert["targets"],
        "result": alert["result"],
        "note": alert["note"],
        "mode": alert["mode"],
    }
