import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelegramThreadStore:
    """Persistent map from one PAPER operation to its Telegram root message."""

    def __init__(self, db_path: str = "data_cache/telegram_threads.db") -> None:
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
            conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_operation_threads (
                operation_key TEXT PRIMARY KEY,
                strategy TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                root_message_id INTEGER NOT NULL,
                root_event_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT
            )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_telegram_thread_strategy "
                "ON telegram_operation_threads(strategy, updated_at)"
            )
            conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_publication_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                event_id TEXT NOT NULL,
                operation_key TEXT NOT NULL,
                symbol TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(strategy, event_id)
            )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_telegram_publication_window "
                "ON telegram_publication_log(strategy, status, created_at)"
            )
            conn.commit()

    def get(self, operation_key: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM telegram_operation_threads WHERE operation_key=?",
                (operation_key,),
            ).fetchone()
        return dict(row) if row else None
    def set_root(
        self,
        operation_key: str,
        strategy: str,
        chat_id: str,
        root_message_id: int,
        root_event_id: str,
    ) -> None:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO telegram_operation_threads
                (operation_key,strategy,chat_id,root_message_id,root_event_id,created_at,updated_at,closed_at)
                VALUES (?,?,?,?,?,?,?,NULL)
                ON CONFLICT(operation_key) DO UPDATE SET
                    updated_at=excluded.updated_at""",
                (operation_key, strategy, chat_id, int(root_message_id), root_event_id, now, now),
            )
            conn.commit()

    def recent_publication_activity(
        self, strategy: str, since_iso: str,
    ) -> list[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM telegram_publication_log
                WHERE strategy=? AND status IN ('RESERVED','PUBLISHED') AND created_at>=?
                ORDER BY created_at ASC""",
                (strategy, since_iso),
            ).fetchall()
        return [dict(row) for row in rows]

    def reserve_publication(
        self, strategy: str, event_id: str, operation_key: str,
        symbol: str, score: float, reason: str,
    ) -> bool:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO telegram_publication_log
                (strategy,event_id,operation_key,symbol,score,reason,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?, 'RESERVED', ?, ?)""",
                (strategy, event_id, operation_key, symbol, float(score), reason, now, now),
            )
            conn.commit()
            return cur.rowcount == 1

    def record_suppression(
        self, strategy: str, event_id: str, operation_key: str,
        symbol: str, score: float, reason: str,
    ) -> None:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO telegram_publication_log
                (strategy,event_id,operation_key,symbol,score,reason,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?, 'SUPPRESSED', ?, ?)""",
                (strategy, event_id, operation_key, symbol, float(score), reason, now, now),
            )
            conn.commit()

    def mark_publication_status(self, strategy: str, event_id: str, status: str) -> None:
        if status not in {'PUBLISHED', 'FAILED'}:
            raise ValueError('invalid publication status')
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE telegram_publication_log SET status=?, updated_at=? WHERE strategy=? AND event_id=?",
                (status, now, strategy, event_id),
            )
            conn.commit()

    def close(self, operation_key: str) -> None:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE telegram_operation_threads SET updated_at=?, closed_at=? WHERE operation_key=?",
                (now, now, operation_key),
            )
            conn.commit()
