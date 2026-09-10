from __future__ import annotations

from collections import Counter
import json
import os
import sqlite3
from typing import Any, Dict, Optional


def _pct(part: int, whole: int) -> float:
    return round((part / whole) * 100.0, 2) if whole else 0.0


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _decode_payload(raw: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        data = json.loads(raw or "{}")
    except Exception:
        return {}, {}
    if not isinstance(data, dict):
        return {}, {}
    if "payload" in data or "levels" in data:
        return dict(data.get("payload") or {}), dict(data.get("levels") or {})
    return data, {}


def _terminal_sign(direction: str, entry: Any, exit_price: Any, points: Any) -> Optional[int]:
    explicit = _to_float(points)
    if explicit is not None:
        return 1 if explicit > 0 else -1 if explicit < 0 else 0
    ep = _to_float(entry)
    xp = _to_float(exit_price)
    if ep is None or xp is None:
        return None
    raw = str(direction or "").upper()
    delta = xp - ep if raw in {"BUY", "LONG", "BULLISH"} else ep - xp
    return 1 if delta > 0 else -1 if delta < 0 else 0


class StrategyPerformanceService:
    def __init__(self, data_dir: str = "data_cache") -> None:
        self.data_dir = data_dir

    def _db(self, name: str) -> str:
        return os.path.join(self.data_dir, name)

    def cycle_theory(self) -> Dict[str, Any]:
        path = self._db("cycle_theory_shadow.db")
        if not os.path.exists(path):
            return {"strategy": "TC", "available": False}
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM cycle_theory_shadow_events ORDER BY event_time, rowid"
        ).fetchall()
        conn.close()
        event_counts = Counter(str(row["event_type"]) for row in rows)
        symbols = {str(row["symbol"]) for row in rows}
        timeframes = {str(row["timeframe"]) for row in rows}
        active: Dict[str, Dict[str, Any]] = {}
        trades = []
        replaced_open_fills = 0
        orphan_terminals = 0

        for row in rows:
            event_type = str(row["event_type"])
            payload, levels = _decode_payload(row["payload_json"])
            symbol = str(row["symbol"])
            if event_type == "LIMIT_FILLED":
                if symbol in active:
                    replaced_open_fills += 1
                active[symbol] = {
                    "symbol": symbol,
                    "timeframe": str(row["timeframe"]),
                    "direction": str(row["direction"]),
                    "entry_time": str(row["event_time"]),
                    "entry": _to_float(levels.get("entry")) or _to_float(payload.get("price")),
                    "initial_stop": _to_float(levels.get("stop")),
                    "partials": [],
                }
                continue
            if event_type == "PARTIAL_EXECUTED" and symbol in active:
                level = int(payload.get("level") or 0)
                active[symbol]["partials"].append({
                    "level": level,
                    "volume": _to_float(payload.get("volume")),
                    "price": _to_float(levels.get(f"target_{level}")),
                    "event_time": str(row["event_time"]),
                })
                continue
            if event_type not in {"STOP_LOSS", "TAKE_PROFIT"}:
                continue
            trade = active.pop(symbol, None)
            if trade is None:
                orphan_terminals += 1
                continue
            exit_price = _to_float(payload.get("price"))
            if exit_price is None:
                exit_price = _to_float(levels.get("stop" if event_type == "STOP_LOSS" else "target_3"))
            sign = _terminal_sign(
                trade["direction"], trade["entry"], exit_price, payload.get("points")
            )
            partials = list(trade["partials"])
            if sign is None:
                result_class = "UNKNOWN"
            elif sign >= 0:
                result_class = "POSITIVE" if sign > 0 else "FLAT"
            elif partials:
                result_class = "AMBIGUOUS_PARTIAL"
            else:
                result_class = "NEGATIVE"
            initial_risk = None
            if trade["entry"] is not None and trade["initial_stop"] is not None:
                initial_risk = abs(trade["entry"] - trade["initial_stop"])
            terminal_r = _to_float(payload.get("r_multiple"))
            if terminal_r is None and initial_risk and exit_price is not None:
                raw = trade["direction"].upper()
                delta = exit_price - trade["entry"] if raw in {"BUY", "LONG", "BULLISH"} else trade["entry"] - exit_price
                terminal_r = round(delta / initial_risk, 8)
            trade.update({
                "exit_type": event_type, "exit_time": str(row["event_time"]),
                "exit_price": exit_price, "terminal_points": _to_float(payload.get("points")),
                "terminal_r": terminal_r, "result_class": result_class,
            })
            trades.append(trade)

        completed = len(trades)
        stop_exits = sum(t["exit_type"] == "STOP_LOSS" for t in trades)
        target_exits = sum(t["exit_type"] == "TAKE_PROFIT" for t in trades)
        positive = sum(t["result_class"] == "POSITIVE" for t in trades)
        negative = sum(t["result_class"] == "NEGATIVE" for t in trades)
        flat = sum(t["result_class"] == "FLAT" for t in trades)
        ambiguous = sum(t["result_class"] == "AMBIGUOUS_PARTIAL" for t in trades)
        unknown = sum(t["result_class"] == "UNKNOWN" for t in trades)
        exact_n = positive + negative + flat
        partial_trade_count = sum(bool(t["partials"]) for t in trades)
        terminal_r_values = [t["terminal_r"] for t in trades if t["terminal_r"] is not None]
        no_partial_r_values = [t["terminal_r"] for t in trades if not t["partials"] and t["terminal_r"] is not None]
        first_time = str(rows[0]["event_time"]) if rows else None
        last_time = str(rows[-1]["event_time"]) if rows else None

        return {
            "strategy": "TC", "strategy_name": "HAGMARTK TDC",
            "available": True, "event_range": {"from": first_time, "to": last_time},
            "total_events": len(rows), "symbols": len(symbols), "timeframes": sorted(timeframes),
            "orders_submitted": int(event_counts.get("ORDER_SUBMITTED", 0)),
            "fills": int(event_counts.get("LIMIT_FILLED", 0)),
            "pullback_missed": int(event_counts.get("PULLBACK_MISSED", 0)),
            "partials": int(event_counts.get("PARTIAL_EXECUTED", 0)),
            "completed_trades": completed, "open_trades": len(active),
            "stop_exits": stop_exits, "target_exits": target_exits,
            "stop_exit_pct": _pct(stop_exits, completed),
            "target_exit_pct": _pct(target_exits, completed),
            "partial_trade_count": partial_trade_count,
            "result_classification": {
                "exact_sample": exact_n,
                "positive": positive,
                "negative": negative,
                "flat": flat,
                "positive_pct_exact_sample": _pct(positive, exact_n),
                "negative_pct_exact_sample": _pct(negative, exact_n),
                "ambiguous_due_to_partials": ambiguous,
                "unknown": unknown,
            },
            "full_trade_r_without_partials": {
                "sample": len(no_partial_r_values),
                "sum_r": round(sum(no_partial_r_values), 6) if no_partial_r_values else None,
                "mean_r": round(sum(no_partial_r_values) / len(no_partial_r_values), 6) if no_partial_r_values else None,
                "scope": "FULL_TRADE_R_ONLY_WHEN_NO_PARTIAL_EXIT_OCCURRED",
            },
            "terminal_leg_r": {
                "sample": len(terminal_r_values),
                "sum_r": round(sum(terminal_r_values), 6) if terminal_r_values else None,
                "mean_r": round(sum(terminal_r_values) / len(terminal_r_values), 6) if terminal_r_values else None,
                "scope": "FINAL_REMAINING_LEG_ONLY_NOT_FULL_TRADE_WHEN_PARTIALS_EXIST",
            },
            "integrity": {
                "matched_terminal_trades": completed,
                "orphan_terminal_events": orphan_terminals,
                "replaced_open_fills": replaced_open_fills,
                "raw_terminal_events": int(event_counts.get("STOP_LOSS", 0) + event_counts.get("TAKE_PROFIT", 0)),
            },
            "interpretation": (
                "Stop/target percentages describe the final exit mechanism. A trailing stop can close a profitable trade. "
                "Trades with profitable partials followed by a negative final leg remain ambiguous until historical volume weighting is reconstructable."
            ),
        }

    def dvp(self) -> Dict[str, Any]:
        path = self._db("shadow_engine.db")
        if not os.path.exists(path):
            return {"strategy": "DVP", "available": False}
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        events = conn.execute(
            "SELECT event_id,current_state,symbol,timeframe,direction,entry_price,initial_stop,target_2R,created_at,updated_at "
            "FROM shadow_events WHERE event_id NOT LIKE 'test_%' ORDER BY created_at"
        ).fetchall()
        evidence_n = conn.execute("SELECT COUNT(*) FROM shadow_hdf_evidence").fetchone()[0]
        observations_n = conn.execute("SELECT COUNT(*) FROM shadow_prospective_observations").fetchone()[0]
        conn.close()
        states = Counter(str(row["current_state"]) for row in events)
        target_n = int(states.get("TARGET_2R", 0))
        stop_n = int(states.get("STOPPED", 0))
        completed = target_n + stop_n
        active_n = int(states.get("ACTIVATED", 0))
        armed_n = int(states.get("ARMED", 0))
        return {
            "strategy": "DVP", "strategy_name": "HAGMARTK DVP", "available": True,
            "operational_events": len(events), "evidence_records": int(evidence_n),
            "prospective_observations": int(observations_n), "activated_open": active_n,
            "armed": armed_n, "completed_trades": completed,
            "target_exits": target_n, "stop_exits": stop_n,
            "target_exit_pct": _pct(target_n, completed), "stop_exit_pct": _pct(stop_n, completed),
            "result_classification": {
                "positive": target_n, "negative": stop_n,
                "positive_pct_completed": _pct(target_n, completed),
                "negative_pct_completed": _pct(stop_n, completed),
            },
            "interpretation": "Only terminal TARGET_2R/STOPPED operational events count as completed DVP trades; evidence observations are not trades.",
        }

    def orb(self) -> Dict[str, Any]:
        path = self._db("orb_shadow.db")
        if not os.path.exists(path):
            return {"strategy": "ORB", "available": False}
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        events = conn.execute("SELECT * FROM orb_shadow_events ORDER BY event_time").fetchall()
        sessions = conn.execute("SELECT * FROM orb_shadow_sessions").fetchall()
        conn.close()
        event_counts = Counter(str(row["event_type"]) for row in events)
        exits = int(event_counts.get("EXIT_FILLED", 0))
        return {
            "strategy": "ORB", "strategy_name": "HAGMARTK ORB", "available": True,
            "sessions": len(sessions), "total_events": len(events),
            "signals": int(event_counts.get("SIGNAL", 0)),
            "entries": int(event_counts.get("ENTRY_FILLED", 0)),
            "rejected_entries": int(event_counts.get("ENTRY_REJECTED", 0)),
            "completed_trades": exits,
            "unresolved_exits": int(event_counts.get("EXIT_UNRESOLVED", 0)),
            "interpretation": "ORB statistics remain prospective only; no retroactive sessions are synthesized.",
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "paper_only": True,
            "real_order_execution_enabled": False,
            "strategies": {
                "DVP": self.dvp(),
                "TC": self.cycle_theory(),
                "ORB": self.orb(),
            },
        }
