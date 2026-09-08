from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


class OrbShadowStore:
    def __init__(self, db_path: str = "data_cache/orb_shadow.db") -> None:
        self.db_path = db_path
        folder = os.path.dirname(db_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
            CREATE TABLE IF NOT EXISTS orb_shadow_sessions (
                session_id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                version TEXT NOT NULL,
                config_hash TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                profile_hash TEXT NOT NULL,
                symbol TEXT NOT NULL,
                provider TEXT NOT NULL,
                account_currency TEXT NOT NULL,
                t0 TEXT NOT NULL,
                t60 TEXT NOT NULL,
                t120 TEXT NOT NULL,
                state TEXT NOT NULL,
                opportunity_consumed INTEGER NOT NULL DEFAULT 0,
                range_high TEXT,
                range_low TEXT,
                signal_id TEXT,
                direction TEXT,
                signal_time TEXT,
                entry_time TEXT,
                entry_price TEXT,
                quantity TEXT,
                stop_price TEXT,
                target_price TEXT,
                risk_cash TEXT,
                exit_time TEXT,
                exit_price TEXT,
                exit_reason TEXT,
                costs_cash TEXT,
                pnl_gross TEXT,
                pnl_net TEXT,
                r_multiple TEXT,
                last_evaluated_close TEXT,
                rejection_reason TEXT,
                data_quality_flags TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS orb_shadow_events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_time TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orb_state ON orb_shadow_sessions(state)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orb_t0 ON orb_shadow_sessions(t0)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orb_events_time ON orb_shadow_events(event_time)")

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orb_shadow_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def upsert_session(self, row: Dict[str, Any]) -> None:
        keys = [
            "session_id", "strategy_id", "version", "config_hash", "profile_id", "profile_hash",
            "symbol", "provider", "account_currency", "t0", "t60", "t120", "state",
            "opportunity_consumed", "range_high", "range_low", "signal_id", "direction", "signal_time",
            "entry_time", "entry_price", "quantity", "stop_price", "target_price", "risk_cash",
            "exit_time", "exit_price", "exit_reason", "costs_cash", "pnl_gross", "pnl_net", "r_multiple",
            "last_evaluated_close", "rejection_reason", "data_quality_flags", "created_at", "updated_at",
        ]
        values = [row.get(key) for key in keys]
        placeholders = ",".join("?" for _ in keys)
        update = ",".join(f"{key}=excluded.{key}" for key in keys[1:])
        sql = (
            f"INSERT INTO orb_shadow_sessions ({','.join(keys)}) VALUES ({placeholders}) "
            f"ON CONFLICT(session_id) DO UPDATE SET {update}"
        )
        with self._lock, self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()

    def append_event(
        self,
        event_id: str,
        session_id: str,
        symbol: str,
        event_type: str,
        event_time: str,
        payload: Dict[str, Any],
        created_at: str,
    ) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO orb_shadow_events
                (event_id, session_id, symbol, event_type, event_time, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event_id, session_id, symbol, event_type, event_time,
                 json.dumps(payload, sort_keys=True, separators=(",", ":")), created_at),
            )
            conn.commit()
            return cur.rowcount > 0

    def open_sessions(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM orb_shadow_sessions WHERE state IN ('OPEN','EXIT_PENDING') ORDER BY t0"
            ).fetchall()
            return [dict(row) for row in rows]

    def sessions_for_t0(self, t0_iso: str) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM orb_shadow_sessions WHERE t0 = ? ORDER BY symbol", (t0_iso,)
            ).fetchall()
            return [dict(row) for row in rows]

    def recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM orb_shadow_events ORDER BY event_time DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.pop("payload_json"))
            except Exception:
                item["payload"] = {}
            result.append(item)
        return result

    def state_counts(self, t0_iso: Optional[str] = None) -> Dict[str, int]:
        with self._lock, self._connect() as conn:
            if t0_iso:
                rows = conn.execute(
                    "SELECT state, COUNT(*) AS n FROM orb_shadow_sessions WHERE t0=? GROUP BY state",
                    (t0_iso,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT state, COUNT(*) AS n FROM orb_shadow_sessions GROUP BY state"
                ).fetchall()
            return {str(row["state"]): int(row["n"]) for row in rows}

    def statistics(self) -> Dict[str, Any]:
        from decimal import Decimal
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT exit_reason, pnl_net, r_multiple FROM orb_shadow_sessions WHERE state='DONE' ORDER BY exit_time"
            ).fetchall()
        n = len(rows)
        r_values = [Decimal(str(row["r_multiple"] or "0")) for row in rows]
        pnl_values = [Decimal(str(row["pnl_net"] or "0")) for row in rows]
        wins = sum(1 for value in pnl_values if value > 0)
        losses = sum(1 for value in pnl_values if value < 0)
        targets = sum(1 for row in rows if str(row["exit_reason"] or "") == "TARGET")
        stops = sum(1 for row in rows if str(row["exit_reason"] or "") == "STOP")
        time_exits = sum(1 for row in rows if str(row["exit_reason"] or "") == "TIME")
        return {
            "resolved_trades": n,
            "wins": wins,
            "losses": losses,
            "target_exits": targets,
            "stop_exits": stops,
            "time_exits": time_exits,
            "expectancy_R": (str(sum(r_values, Decimal("0")) / Decimal(n)) if n else None),
            "net_pnl_sum": str(sum(pnl_values, Decimal("0"))),
            "events_total": self.total_events(),
            "paper_only": True,
            "real_order_execution_enabled": False,
        }

    def total_events(self) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM orb_shadow_events").fetchone()
            return int(row["n"] if row else 0)
