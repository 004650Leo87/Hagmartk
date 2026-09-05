from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CycleTheoryShadowStore:
    """Isolated prospective ledger for Cycle Theory V111 Shadow observation."""

    def __init__(self, db_path: str = "data_cache/cycle_theory_shadow.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS cycle_theory_shadow_events (
                event_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                parameter_hash TEXT NOT NULL,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                event_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                event_time TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cycle_shadow_symbol_time
                ON cycle_theory_shadow_events(symbol, event_time);
            CREATE TABLE IF NOT EXISTS cycle_theory_shadow_policy (
                symbol TEXT PRIMARY KEY,
                week_key TEXT NOT NULL,
                opening_trade_seen INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cycle_theory_shadow_runtime (
                symbol TEXT PRIMARY KEY,
                snapshot_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            conn.commit()

    def add_event(self, event: dict[str, Any]) -> bool:
        with self._conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO cycle_theory_shadow_events
                    (event_id,candidate_id,parameter_hash,symbol,market,timeframe,event_type,
                     direction,event_time,payload_json,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (event["event_id"], event["candidate_id"], event["parameter_hash"],
                     event["symbol"], event["market"], event["timeframe"], event["event_type"],
                     event["direction"], event["event_time"],
                     json.dumps(event["payload"], ensure_ascii=False, sort_keys=True, default=str), _utc_now()),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_policy(self, symbol: str, week_key: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT week_key, opening_trade_seen FROM cycle_theory_shadow_policy WHERE symbol=?",
                (symbol,),
            ).fetchone()
        return bool(row and row["week_key"] == week_key and row["opening_trade_seen"])

    def set_opening_trade_seen(self, symbol: str, week_key: str, seen: bool = True) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO cycle_theory_shadow_policy(symbol,week_key,opening_trade_seen,updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(symbol) DO UPDATE SET week_key=excluded.week_key,
                    opening_trade_seen=excluded.opening_trade_seen, updated_at=excluded.updated_at""",
                (symbol, week_key, int(seen), _utc_now()),
            )
            conn.commit()

    def save_runtime(self, symbol: str, snapshot: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO cycle_theory_shadow_runtime(symbol,snapshot_json,updated_at)
                VALUES (?,?,?)
                ON CONFLICT(symbol) DO UPDATE SET snapshot_json=excluded.snapshot_json,
                    updated_at=excluded.updated_at""",
                (symbol, json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str), _utc_now()),
            )
            conn.commit()

    def load_runtime(self, symbol: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM cycle_theory_shadow_runtime WHERE symbol=?", (symbol,)
            ).fetchone()
        return json.loads(row["snapshot_json"]) if row else None

    def summary(self) -> dict[str, Any]:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM cycle_theory_shadow_events").fetchone()["n"]
            last = conn.execute(
                "SELECT event_time,symbol,timeframe,event_type FROM cycle_theory_shadow_events "
                "ORDER BY event_time DESC LIMIT 1"
            ).fetchone()
        return {"events": int(total), "last_event": dict(last) if last else None}
