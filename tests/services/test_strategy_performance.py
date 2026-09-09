import json
import sqlite3

from backend.services.strategy_performance import StrategyPerformanceService


def _cycle_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE cycle_theory_shadow_events (
        event_id TEXT PRIMARY KEY,candidate_id TEXT,parameter_hash TEXT,symbol TEXT,
        market TEXT,timeframe TEXT,event_type TEXT,direction TEXT,event_time TEXT,
        payload_json TEXT,created_at TEXT)""")
    return conn


def _add_cycle(conn, event_id, symbol, kind, direction, at, payload=None, levels=None):
    raw = json.dumps({"payload": payload or {}, "levels": levels or {}})
    conn.execute(
        "INSERT INTO cycle_theory_shadow_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, "c", "h", symbol, "TEST", "M5", kind, direction, at, raw, at),
    )


def test_cycle_summary_distinguishes_exit_mechanism_from_profitability(tmp_path):
    conn = _cycle_db(tmp_path / "cycle_theory_shadow.db")
    levels = {"entry": 100, "stop": 90, "target_1": 110, "target_2": 120, "target_3": 130}
    _add_cycle(conn, "f1", "A", "LIMIT_FILLED", "BUY", "2026-01-01T00:00:00+00:00", {"price": 100}, levels)
    _add_cycle(conn, "s1", "A", "STOP_LOSS", "BUY", "2026-01-01T00:05:00+00:00", {"price": 105, "points": 5}, levels)
    _add_cycle(conn, "f2", "B", "LIMIT_FILLED", "BUY", "2026-01-01T00:10:00+00:00", {"price": 100}, levels)
    _add_cycle(conn, "s2", "B", "STOP_LOSS", "BUY", "2026-01-01T00:15:00+00:00", {"price": 90, "points": -10}, levels)
    sell_levels = {"entry": 100, "stop": 110, "target_1": 90, "target_2": 80, "target_3": 70}
    _add_cycle(conn, "f3", "C", "LIMIT_FILLED", "SELL", "2026-01-01T00:20:00+00:00", {"price": 100}, sell_levels)
    _add_cycle(conn, "t3", "C", "TAKE_PROFIT", "SELL", "2026-01-01T00:25:00+00:00", {"price": 80, "points": 20}, sell_levels)
    conn.commit(); conn.close()

    result = StrategyPerformanceService(str(tmp_path)).cycle_theory()
    assert result["completed_trades"] == 3
    assert result["stop_exits"] == 2
    assert result["target_exits"] == 1
    assert result["stop_exit_pct"] == 66.67
    assert result["result_classification"]["positive"] == 2
    assert result["result_classification"]["negative"] == 1
    assert result["result_classification"]["positive_pct_exact_sample"] == 66.67
    assert result["integrity"]["orphan_terminal_events"] == 0


def test_cycle_summary_marks_negative_final_leg_after_partial_as_ambiguous(tmp_path):
    conn = _cycle_db(tmp_path / "cycle_theory_shadow.db")
    levels = {"entry": 100, "stop": 90, "target_1": 110, "target_2": 120, "target_3": 130}
    _add_cycle(conn, "f", "A", "LIMIT_FILLED", "BUY", "2026-01-01T00:00:00+00:00", {"price": 100}, levels)
    _add_cycle(conn, "p", "A", "PARTIAL_EXECUTED", "BUY", "2026-01-01T00:02:00+00:00", {"level": 1, "volume": 1}, levels)
    _add_cycle(conn, "s", "A", "STOP_LOSS", "BUY", "2026-01-01T00:05:00+00:00", {"price": 95, "points": -5}, levels)
    conn.commit(); conn.close()

    result = StrategyPerformanceService(str(tmp_path)).cycle_theory()
    assert result["completed_trades"] == 1
    assert result["partial_trade_count"] == 1
    assert result["result_classification"]["ambiguous_due_to_partials"] == 1
    assert result["result_classification"]["exact_sample"] == 0
