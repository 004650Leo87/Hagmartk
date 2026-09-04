from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
import numpy as np

from backend.domain.shadow_models import (
    HDFEvidence,
    ShadowEvent,
    ShadowScannerState,
    ShadowState,
    ShadowStatistics,
    ShadowTransition,
)


class ShadowStoreRepository:
    """Repositório de persistência SQLite para o Event Store do Shadow Mode."""

    def __init__(self, db_path: str = "data_cache/shadow_engine.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Tabela shadow_events
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_events (
                event_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                candidate_version TEXT,
                parameter_hash TEXT,
                symbol TEXT,
                asset_class TEXT,
                timeframe TEXT,
                direction TEXT,
                pattern_type TEXT,
                pivot_1_time TEXT,
                pivot_1_price REAL,
                pivot_1_rsi REAL,
                pivot_2_time TEXT,
                pivot_2_price REAL,
                pivot_2_rsi REAL,
                divergence_confirmed_at TEXT,
                relative_volume REAL,
                volume_source TEXT,
                confluence_time TEXT,
                armed_at TEXT,
                activation_level REAL,
                activated_at TEXT,
                entry_price REAL,
                initial_stop REAL,
                target_2R REAL,
                initial_risk REAL,
                current_state TEXT,
                milestone_1r_reached INTEGER,
                mfe_r_live REAL,
                mae_r_live REAL,
                bars_since_activation INTEGER,
                market_source TEXT,
                broker TEXT,
                market_candle_time TEXT,
                received_at TEXT,
                processed_at TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata_json TEXT,
                evidence_json TEXT,
                dedup_key TEXT UNIQUE
            )
            """)

            # Tabela shadow_transitions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_transitions (
                transition_id TEXT PRIMARY KEY,
                event_id TEXT,
                from_state TEXT,
                to_state TEXT,
                timestamp TEXT,
                candle_timestamp TEXT,
                market_price REAL,
                reason TEXT,
                FOREIGN KEY(event_id) REFERENCES shadow_events(event_id)
            )
            """)

            # Tabela shadow_scanner_state
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_scanner_state (
                key TEXT PRIMARY KEY,
                candidate_id TEXT,
                symbol TEXT,
                timeframe TEXT,
                enabled INTEGER,
                last_processed_candle TEXT,
                last_scan_at TEXT,
                scanner_status TEXT,
                error_message TEXT,
                scan_cycle_count_total INTEGER DEFAULT 0,
                evaluation_count_total INTEGER DEFAULT 0,
                last_evaluated_candle_time TEXT DEFAULT '',
                last_evaluation_at TEXT DEFAULT '',
                last_result_stage TEXT DEFAULT 'NONE'
            )
            """)

            for col, col_type in [
                ("scan_cycle_count_total", "INTEGER DEFAULT 0"),
                ("evaluation_count_total", "INTEGER DEFAULT 0"),
                ("last_evaluated_candle_time", "TEXT DEFAULT ''"),
                ("last_evaluation_at", "TEXT DEFAULT ''"),
                ("last_result_stage", "TEXT DEFAULT 'NONE'"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE shadow_scanner_state ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

            # Tabela shadow_session para persistência de shadow_started_at
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_session (
                candidate_id TEXT PRIMARY KEY,
                started_at TEXT,
                enabled INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """)

            # Independent operational-telemetry T0. Does not change Shadow/evidence T0.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_telemetry_session (
                candidate_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            # Independent HDF-evidence T0. Used to start a clean immutable evidence cohort
            # without resetting the broader Shadow session.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_evidence_session (
                candidate_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            # Provider support snapshot: configured universe vs symbols actually available in runtime.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_provider_support (
                symbol TEXT PRIMARY KEY,
                supported INTEGER NOT NULL,
                reason TEXT NOT NULL,
                checked_at TEXT NOT NULL
            )
            """)

            # Tabela shadow_scanner_telemetry para observabilidade operacional V1
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_scanner_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                expected_checks INTEGER DEFAULT 0,
                successful_checks INTEGER DEFAULT 0,
                failed_checks INTEGER DEFAULT 0,
                last_success_at TEXT,
                last_failure_at TEXT,
                last_error_code TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(candidate_id, window_start, symbol, timeframe)
            )
            """)

            # Tabela shadow_prospective_observations para acúmulo prospectivo confiável
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_prospective_observations (
                observation_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                candidate_version TEXT NOT NULL,
                parameter_hash TEXT NOT NULL,
                symbol TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                window_time TEXT NOT NULL,
                observational_status TEXT NOT NULL,
                evidence_state TEXT NOT NULL,
                reason_codes_json TEXT NOT NULL,
                sample_size INTEGER DEFAULT 0,
                scanner_coverage REAL,
                expectancy_r REAL,
                win_rate REAL,
                profit_factor REAL,
                max_drawdown REAL,
                quality_context TEXT NOT NULL,
                degraded_flag INTEGER DEFAULT 0,
                contradictions_json TEXT,
                observed_at TEXT NOT NULL,
                UNIQUE(candidate_id, symbol, timeframe, window_time)
            )
            """)

            # Tabela shadow_evidence_transitions para histórico de transição de evidência
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_evidence_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                transitioned_at TEXT NOT NULL
            )
            """)

            # Tabela shadow_hdf_evidence para armazenamento independente de evidências matemáticas HDF
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_hdf_evidence (
                evidence_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                direction TEXT NOT NULL,
                pivot_1_time TEXT NOT NULL,
                pivot_1_price REAL NOT NULL,
                pivot_1_rsi REAL NOT NULL,
                pivot_2_time TEXT NOT NULL,
                pivot_2_price REAL NOT NULL,
                pivot_2_rsi REAL NOT NULL,
                divergence_confirmed INTEGER DEFAULT 1,
                relative_volume REAL DEFAULT 0.0,
                volume_pass INTEGER DEFAULT 0,
                pattern_type TEXT DEFAULT 'NONE',
                pattern_pass INTEGER DEFAULT 0,
                pattern_policy TEXT DEFAULT 'SAME_BAR',
                variant_stage TEXT DEFAULT 'HDF_D',
                candidate_created INTEGER DEFAULT 0,
                armed INTEGER DEFAULT 0,
                activated INTEGER DEFAULT 0,
                event_id TEXT,
                reason_codes_json TEXT DEFAULT '[]',
                source TEXT NOT NULL DEFAULT 'LIVE_PROSPECTIVE',
                is_test INTEGER DEFAULT 0,
                detected_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(symbol, timeframe, pivot_2_time, direction)
            )
            """)

            # Independent Fibonacci research telemetry; never promotes candidate state.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_fibonacci_telemetry (
                telemetry_id TEXT PRIMARY KEY,
                research_scope TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                occurrence_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                direction TEXT NOT NULL,
                mode TEXT NOT NULL,
                role TEXT NOT NULL,
                policy_id TEXT NOT NULL,
                decision_time TEXT NOT NULL,
                decision_status TEXT NOT NULL,
                decision_reason TEXT NOT NULL,
                anchor_a_time TEXT NOT NULL,
                anchor_a_price REAL,
                anchor_a_confirmed_at TEXT NOT NULL,
                anchor_b_time TEXT NOT NULL,
                anchor_b_price REAL,
                anchor_b_confirmed_at TEXT NOT NULL,
                levels_json TEXT NOT NULL,
                matched_levels_json TEXT NOT NULL,
                evidence_snapshot_json TEXT NOT NULL DEFAULT '{}',
                activated INTEGER DEFAULT 0,
                activation_level REAL DEFAULT 0.0,
                entry_time TEXT NOT NULL,
                entry_price REAL DEFAULT 0.0,
                stop_price REAL DEFAULT 0.0,
                target_outcomes_json TEXT NOT NULL,
                last_observed_candle TEXT NOT NULL,
                source TEXT NOT NULL,
                is_test INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(symbol, timeframe, direction, decision_time, mode, source, is_test)
            )
            """)

            try:
                cursor.execute("ALTER TABLE shadow_hdf_evidence ADD COLUMN source TEXT NOT NULL DEFAULT 'LIVE_PROSPECTIVE'")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE shadow_fibonacci_telemetry ADD COLUMN evidence_snapshot_json TEXT NOT NULL DEFAULT '{}'")
            except Exception:
                pass

            conn.commit()

    def save_shadow_session(self, candidate_id: str, started_at: str, enabled: bool = True) -> None:
        """Persiste o instante de início (shadow_started_at) e estado da sessão Shadow."""
        from backend.core.time_utils import now_utc_str
        now_str = now_utc_str()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO shadow_session (candidate_id, started_at, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    started_at = excluded.started_at,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (candidate_id, started_at, 1 if enabled else 0, now_str, now_str),
            )
            conn.commit()

    def get_shadow_session(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Recupera os dados da sessão Shadow persistida para o candidato especificado."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shadow_session WHERE candidate_id = ?", (candidate_id,))
            r = cursor.fetchone()
            if r:
                return {
                    "candidate_id": r["candidate_id"],
                    "started_at": r["started_at"],
                    "enabled": bool(r["enabled"]),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
            return None

    def save_telemetry_session(self, candidate_id: str, started_at: str) -> None:
        from backend.core.time_utils import now_utc_str
        now_str = now_utc_str()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO shadow_telemetry_session (candidate_id, started_at, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    started_at = excluded.started_at,
                    updated_at = excluded.updated_at
                """,
                (candidate_id, started_at, now_str, now_str),
            )
            conn.commit()

    def get_telemetry_session(self, candidate_id: str) -> Optional[Dict[str, str]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT candidate_id, started_at, created_at, updated_at FROM shadow_telemetry_session WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                return None
            return {key: str(row[key]) for key in ("candidate_id", "started_at", "created_at", "updated_at")}

    def save_evidence_session(self, candidate_id: str, started_at: str) -> None:
        from backend.core.time_utils import now_utc_str
        now_str = now_utc_str()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO shadow_evidence_session (candidate_id, started_at, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    started_at = excluded.started_at,
                    updated_at = excluded.updated_at
                """,
                (candidate_id, started_at, now_str, now_str),
            )
            conn.commit()

    def get_evidence_session(self, candidate_id: str) -> Optional[Dict[str, str]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT candidate_id, started_at, created_at, updated_at FROM shadow_evidence_session WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                return None
            return {key: str(row[key]) for key in ("candidate_id", "started_at", "created_at", "updated_at")}

    def save_provider_support(self, symbol: str, supported: bool, reason: str, checked_at: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO shadow_provider_support (symbol, supported, reason, checked_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    supported = excluded.supported,
                    reason = excluded.reason,
                    checked_at = excluded.checked_at
                """,
                (symbol.upper(), 1 if supported else 0, reason, checked_at),
            )
            conn.commit()

    def get_provider_support(self) -> Dict[str, Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, supported, reason, checked_at FROM shadow_provider_support")
            rows = cursor.fetchall()
            return {
                str(r["symbol"]): {
                    "supported": bool(r["supported"]),
                    "reason": str(r["reason"]),
                    "checked_at": str(r["checked_at"]),
                }
                for r in rows
            }

    def save_event(self, evt: ShadowEvent, dedup_key: str = "") -> bool:
        """Salva um novo evento Shadow se não existir (idempotência via dedup_key)."""
        if not dedup_key:
            dedup_key = evt.compute_deduplication_key(evt.current_state)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                INSERT INTO shadow_events (
                    event_id, candidate_id, candidate_version, parameter_hash,
                    symbol, asset_class, timeframe, direction, pattern_type,
                    pivot_1_time, pivot_1_price, pivot_1_rsi,
                    pivot_2_time, pivot_2_price, pivot_2_rsi,
                    divergence_confirmed_at, relative_volume, volume_source,
                    confluence_time, armed_at, activation_level,
                    activated_at, entry_price, initial_stop, target_2R, initial_risk,
                    current_state, milestone_1r_reached, mfe_r_live, mae_r_live,
                    bars_since_activation, market_source, broker,
                    market_candle_time, received_at, processed_at,
                    created_at, updated_at, metadata_json, evidence_json, dedup_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        evt.event_id, evt.candidate_id, evt.candidate_version, evt.parameter_hash,
                        evt.symbol, evt.asset_class, evt.timeframe, evt.direction, evt.pattern_type,
                        evt.pivot_1_time, evt.pivot_1_price, evt.pivot_1_rsi,
                        evt.pivot_2_time, evt.pivot_2_price, evt.pivot_2_rsi,
                        evt.divergence_confirmed_at, evt.relative_volume, evt.volume_source,
                        evt.confluence_time, evt.armed_at, evt.activation_level,
                        evt.activated_at, evt.entry_price, evt.initial_stop, evt.target_2R, evt.initial_risk,
                        evt.current_state, 1 if evt.milestone_1r_reached else 0, evt.mfe_r_live, evt.mae_r_live,
                        evt.bars_since_activation, evt.market_source, evt.broker,
                        evt.market_candle_time, evt.received_at, evt.processed_at,
                        evt.created_at, evt.updated_at,
                        json.dumps(evt.metadata),
                        json.dumps(evt.evidence) if evt.evidence else "",
                        dedup_key,
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Duplicação ignorada de forma idempotente
                return False

    def update_event(self, evt: ShadowEvent) -> None:
        """Atualiza o estado e métricas dinâmicas de um evento existente."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
            UPDATE shadow_events SET
                current_state = ?,
                milestone_1r_reached = ?,
                activated_at = ?,
                entry_price = ?,
                initial_risk = ?,
                mfe_r_live = ?,
                mae_r_live = ?,
                bars_since_activation = ?,
                updated_at = ?,
                metadata_json = ?,
                evidence_json = ?
            WHERE event_id = ?
            """,
                (
                    evt.current_state,
                    1 if evt.milestone_1r_reached else 0,
                    evt.activated_at,
                    evt.entry_price,
                    evt.initial_risk,
                    evt.mfe_r_live,
                    evt.mae_r_live,
                    evt.bars_since_activation,
                    evt.updated_at,
                    json.dumps(evt.metadata),
                    json.dumps(evt.evidence) if evt.evidence else "",
                    evt.event_id,
                ),
            )
            conn.commit()

    def get_event(self, event_id: str) -> Optional[ShadowEvent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shadow_events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_event(row)
            return None

    def list_active_events(self) -> List[ShadowEvent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shadow_events WHERE current_state IN ('ARMED', 'ACTIVATED')")
            rows = cursor.fetchall()
            return [self._row_to_event(r) for r in rows]

    def list_history_events(self) -> List[ShadowEvent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shadow_events ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [self._row_to_event(r) for r in rows]

    def list_history_events_paginated(self, limit: int = 20, offset: int = 0) -> List[ShadowEvent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM shadow_events ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cursor.fetchall()
            return [self._row_to_event(r) for r in rows]

    def count_events(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM shadow_events")
            row = cursor.fetchone()
            return row[0] if row else 0

    def add_transition(self, trans: ShadowTransition) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
            INSERT INTO shadow_transitions (
                transition_id, event_id, from_state, to_state, timestamp, candle_timestamp, market_price, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    trans.transition_id, trans.event_id, trans.from_state, trans.to_state,
                    trans.timestamp, trans.candle_timestamp, trans.market_price, trans.reason,
                ),
            )
            conn.commit()

    def get_transitions(self, event_id: str) -> List[ShadowTransition]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shadow_transitions WHERE event_id = ? ORDER BY timestamp ASC", (event_id,))
            rows = cursor.fetchall()
            return [
                ShadowTransition(
                    transition_id=r["transition_id"], event_id=r["event_id"], from_state=r["from_state"],
                    to_state=r["to_state"], timestamp=r["timestamp"], candle_timestamp=r["candle_timestamp"],
                    market_price=r["market_price"], reason=r["reason"],
                )
                for r in rows
            ]

    def save_scanner_state(self, state: ShadowScannerState) -> None:
        key = f"{state.candidate_id}_{state.symbol}_{state.timeframe}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
            INSERT OR REPLACE INTO shadow_scanner_state (
                key, candidate_id, symbol, timeframe, enabled, last_processed_candle, last_scan_at,
                scanner_status, error_message, scan_cycle_count_total, evaluation_count_total,
                last_evaluated_candle_time, last_evaluation_at, last_result_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    key, state.candidate_id, state.symbol, state.timeframe, 1 if state.enabled else 0,
                    state.last_processed_candle, state.last_scan_at, state.scanner_status, state.error_message,
                    state.scan_cycle_count_total, state.evaluation_count_total,
                    state.last_evaluated_candle_time, state.last_evaluation_at, state.last_result_stage,
                ),
            )
            conn.commit()

    def get_scanner_state(self, candidate_id: str, symbol: str, timeframe: str) -> Optional[ShadowScannerState]:
        key = f"{candidate_id}_{symbol}_{timeframe}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shadow_scanner_state WHERE key = ?", (key,))
            r = cursor.fetchone()
            if r:
                return ShadowScannerState(
                    candidate_id=r["candidate_id"], symbol=r["symbol"], timeframe=r["timeframe"],
                    enabled=bool(r["enabled"]), last_processed_candle=r["last_processed_candle"],
                    last_scan_at=r["last_scan_at"], scanner_status=r["scanner_status"], error_message=r["error_message"] or "",
                    scan_cycle_count_total=r["scan_cycle_count_total"] if "scan_cycle_count_total" in r.keys() and r["scan_cycle_count_total"] is not None else 0,
                    evaluation_count_total=r["evaluation_count_total"] if "evaluation_count_total" in r.keys() and r["evaluation_count_total"] is not None else 0,
                    last_evaluated_candle_time=r["last_evaluated_candle_time"] if "last_evaluated_candle_time" in r.keys() and r["last_evaluated_candle_time"] is not None else "",
                    last_evaluation_at=r["last_evaluation_at"] if "last_evaluation_at" in r.keys() and r["last_evaluation_at"] is not None else "",
                    last_result_stage=r["last_result_stage"] if "last_result_stage" in r.keys() and r["last_result_stage"] is not None else "NONE",
                )
            return None

    def _get_live_candidates(
        self,
        cursor: Any,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retorna exclusivamente os candidatos VIVOS (não expirados) respeitando a janela
        oficial de ativação da estratégia congelada (max_activation_bars = 5 candles).
        Preserva 100% os registros históricos no SQLite.
        """
        from backend.core.time_utils import parse_utc_timestamp, now_utc_datetime

        now_dt = now_utc_datetime()
        TIMEFRAME_BAR_SECONDS = {
            "M1": 60,
            "M5": 300,
            "M15": 900,
            "M30": 1800,
            "H1": 3600,
            "H4": 14400,
            "D1": 86400,
        }
        MAX_ACTIVATION_BARS = 5  # Regra oficial da estratégia congelada Candidate V1

        query = (
            "SELECT evidence_id, symbol, timeframe, direction, variant_stage, "
            "volume_pass, pattern_pass, pattern_type, relative_volume, detected_at, created_at, pivot_2_time "
            "FROM shadow_hdf_evidence "
            "WHERE candidate_created = 1 AND is_test = 0"
        )
        params: List[Any] = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        c_rows = cursor.fetchall()

        live_items = []
        for r in c_rows:
            tf = r["timeframe"].upper()
            bar_sec = TIMEFRAME_BAR_SECONDS.get(tf, 900)
            max_validity_sec = MAX_ACTIVATION_BARS * bar_sec

            ts_str = r["created_at"] or r["detected_at"] or r["pivot_2_time"]
            dt = parse_utc_timestamp(ts_str)
            if dt is None:
                continue

            age_sec = (now_dt - dt).total_seconds()
            if age_sec < 0:
                age_sec = 0

            # Se a idade em segundos ultrapassar o limite de max_activation_bars candles, o candidato é STALE/EXPIRED
            if age_sec > max_validity_sec:
                continue

            confluences = ["Divergência HDF_D"]
            if r["volume_pass"]:
                vol_val = round(float(r["relative_volume"] or 0.0), 2)
                confluences.append(f"Volume ({vol_val}x)" if vol_val > 0 else "Volume")
            if r["pattern_pass"]:
                pat_name = r["pattern_type"] if r["pattern_type"] and r["pattern_type"] != "NONE" else "Padrão"
                confluences.append(f"Padrão ({pat_name})")

            pending = []
            if not r["volume_pass"]:
                pending.append("Filtro de Volume")
            if not r["pattern_pass"]:
                pending.append("Padrão de Reversão")

            live_items.append({
                "evidence_id": r["evidence_id"],
                "symbol": r["symbol"],
                "timeframe": r["timeframe"],
                "direction": r["direction"],
                "stage": r["variant_stage"] or "CANDIDATO",
                "confluences": confluences,
                "pending": pending,
                "updated_at": r["created_at"] or r["detected_at"],
            })

        return live_items

    def get_shadow_heartbeat(self, candidate_id: str = "hdf_dvp_exit_2r") -> Dict[str, Any]:
        """Retorna telemetria e diagnósticos de execução autônoma do Shadow Scanner em tempo real."""
        from backend.services.shadow_scanner import SHADOW_ASSETS, SHADOW_TIMEFRAMES, get_asset_class
        from backend.core.time_utils import now_utc_datetime, now_utc_str, parse_utc_timestamp

        now_dt = now_utc_datetime()
        now_str = now_utc_str()

        STALE_THRESHOLD_SECONDS = {
            "M15": 2700,    # 45 minutos
            "H1": 10800,    # 3 horas
            "H4": 43200,    # 12 horas
        }

        funnel = self.get_funnel_telemetry()

        scanners_list = []
        tot_cycles = 0
        tot_evaluations = 0
        running_cnt = 0
        waiting_cnt = 0
        stale_cnt = 0
        error_cnt = 0

        for sym in SHADOW_ASSETS:
            for tf in SHADOW_TIMEFRAMES:
                st = self.get_scanner_state(candidate_id, sym, tf)
                scan_cycles = st.scan_cycle_count_total if st else 0
                evaluations = st.evaluation_count_total if st else 0
                status_val = st.scanner_status if st else "RUNNING"
                last_closed = st.last_processed_candle if st else ""
                last_eval_candle = st.last_evaluated_candle_time if st else last_closed
                last_eval_at = st.last_evaluation_at if st else (st.last_scan_at if st else "")
                last_stage = st.last_result_stage if st else "NONE"
                err_msg = st.error_message if st else None

                tot_cycles += scan_cycles
                tot_evaluations += evaluations

                last_dt = parse_utc_timestamp(last_eval_at)
                age_seconds = int((now_dt - last_dt).total_seconds()) if last_dt is not None else 999999
                max_stale_sec = STALE_THRESHOLD_SECONDS.get(tf.upper(), 2700)

                is_stale = age_seconds > max_stale_sec if last_dt is not None else False

                if status_val == "ERROR":
                    error_cnt += 1
                elif is_stale:
                    stale_cnt += 1
                elif status_val == "WAITING_NEW_CANDLE":
                    waiting_cnt += 1
                else:
                    running_cnt += 1

                scanners_list.append({
                    "symbol": sym,
                    "asset_class": get_asset_class(sym),
                    "timeframe": tf,
                    "status": status_val,
                    "last_closed_candle": last_closed,
                    "last_evaluated_candle": last_eval_candle,
                    "last_evaluation_at": last_eval_at,
                    "evaluation_count_total": evaluations,
                    "scan_cycle_count_total": scan_cycles,
                    "last_result_stage": last_stage,
                    "is_stale": is_stale,
                    "last_error": err_msg,
                })

        # Buscar lista detalhada dos candidatos VIVOS (não expirados) para a experiência de hover
        with self._get_connection() as conn:
            cursor = conn.cursor()
            candidate_items = self._get_live_candidates(cursor)

        return {
            "generated_at": now_str,
            "registered": len(scanners_list),
            "running": running_cnt,
            "waiting_new_candle": waiting_cnt,
            "stale": stale_cnt,
            "errors": error_cnt,
            "totals": {
                "scan_cycles": tot_cycles,
                "evaluations": tot_evaluations,
                "pivots": funnel.get("pivots", 0),
                "hdf_d": funnel.get("hdf_d", 0),
                "hdf_dv": funnel.get("hdf_dv", 0),
                "hdf_dp": funnel.get("hdf_dp", 0),
                "hdf_dvp": funnel.get("hdf_dvp", 0),
                "candidates": len(candidate_items),
                "candidate_items": candidate_items,
                "armed": funnel.get("armed", 0),
                "activated": funnel.get("activated", 0),
                "expired": funnel.get("expired", 0),
                "stopped": funnel.get("stopped", 0),
                "target_2r": funnel.get("target_2r", 0),
            },
            "scanners": scanners_list,
        }

    def get_shadow_statistics(self, started_at: str = "") -> ShadowStatistics:
        """Calcula estatísticas prospectivas estritas do Shadow Mode (começando do zero)."""
        events = self.list_history_events()
        stats = ShadowStatistics(shadow_started_at=started_at)

        if not events:
            return stats

        stats.total_events_detected = len(events)
        stats.armed_count = sum(1 for e in events if e.armed_at != "")
        stats.activated_count = sum(1 for e in events if e.activated_at != "")

        wins = [e for e in events if e.current_state == "TARGET_2R"]
        losses = [e for e in events if e.current_state == "STOPPED"]
        opens = [e for e in events if e.current_state == "ACTIVATED"]
        expired = [e for e in events if e.current_state == "EXPIRED"]
        invalidated = [e for e in events if e.current_state == "INVALIDATED"]

        stats.targets_reached_count = len(wins)
        stats.stops_reached_count = len(losses)
        stats.open_count = len(opens)
        stats.expired_count = len(expired)
        stats.invalidated_count = len(invalidated)

        n_finished = len(wins) + len(losses)
        stats.win_rate_shadow = (len(wins) / n_finished * 100.0) if n_finished > 0 else 0.0

        # PnL líquido em R (com custo 0.03R por trade)
        net_r_list = []
        for e in wins:
            net_r_list.append(2.0 - 0.03)  # EXIT_2R = 2R bruto - 0.03R custo
        for e in losses:
            net_r_list.append(-1.0 - 0.03) # Stop = -1R bruto - 0.03R custo

        stats.net_r_shadow = float(sum(net_r_list))
        stats.expectancy_r_shadow = float(np.mean(net_r_list)) if net_r_list else 0.0

        w_sum = sum(r for r in net_r_list if r > 0)
        l_sum = abs(sum(r for r in net_r_list if r < 0))
        stats.profit_factor_shadow = float(w_sum / l_sum) if l_sum > 0 else (float(w_sum) if w_sum > 0 else 0.0)

        # Max Drawdown
        if net_r_list:
            eq = np.cumsum([0.0] + net_r_list)
            pk = np.maximum.accumulate(eq)
            stats.max_drawdown_r_shadow = float(np.max(pk - eq))

        mfes = [e.mfe_r_live for e in events if e.activated_at != ""]
        maes = [e.mae_r_live for e in events if e.activated_at != ""]
        holdings = [e.bars_since_activation for e in events if e.activated_at != ""]

        stats.mfe_median_r = float(np.median(mfes)) if mfes else 0.0
        stats.mae_median_r = float(np.median(maes)) if maes else 0.0
        stats.average_holding_bars = float(np.mean(holdings)) if holdings else 0.0

        return stats

    def _row_to_event(self, r: sqlite3.Row) -> ShadowEvent:
        meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
        evi = json.loads(r["evidence_json"]) if r["evidence_json"] else None
        return ShadowEvent(
            event_id=r["event_id"], candidate_id=r["candidate_id"], candidate_version=r["candidate_version"],
            parameter_hash=r["parameter_hash"], symbol=r["symbol"], asset_class=r["asset_class"],
            timeframe=r["timeframe"], direction=r["direction"], pattern_type=r["pattern_type"],
            pivot_1_time=r["pivot_1_time"], pivot_1_price=r["pivot_1_price"], pivot_1_rsi=r["pivot_1_rsi"],
            pivot_2_time=r["pivot_2_time"], pivot_2_price=r["pivot_2_price"], pivot_2_rsi=r["pivot_2_rsi"],
            divergence_confirmed_at=r["divergence_confirmed_at"], relative_volume=r["relative_volume"],
            volume_source=r["volume_source"], confluence_time=r["confluence_time"], armed_at=r["armed_at"],
            activation_level=r["activation_level"], activated_at=r["activated_at"], entry_price=r["entry_price"],
            initial_stop=r["initial_stop"], target_2R=r["target_2R"], initial_risk=r["initial_risk"],
            current_state=r["current_state"], milestone_1r_reached=bool(r["milestone_1r_reached"]),
            mfe_r_live=r["mfe_r_live"], mae_r_live=r["mae_r_live"], bars_since_activation=r["bars_since_activation"],
            market_source=r["market_source"], broker=r["broker"], market_candle_time=r["market_candle_time"],
            received_at=r["received_at"], processed_at=r["processed_at"], created_at=r["created_at"],
            updated_at=r["updated_at"], metadata=meta, evidence=evi,
        )

    @staticmethod
    def _expected_checks_for_window(candidate_id: str, timeframe: str, now_dt, cursor) -> int:
        """Expected closed-candle slots elapsed in the current UTC hour.

        The lower bound respects both Shadow T0 and the independent telemetry T0.
        """
        from datetime import timedelta
        from backend.core.time_utils import parse_utc_timestamp

        tf = timeframe.upper()
        tf_minutes = {"M15": 15, "H1": 60, "H4": 240}.get(tf)
        if tf_minutes is None:
            return 0

        hour_start = now_dt.replace(minute=0, second=0, microsecond=0)
        lower_bound = hour_start

        for table in ("shadow_session", "shadow_telemetry_session"):
            row = cursor.execute(
                f"SELECT started_at FROM {table} WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            dt = parse_utc_timestamp(row[0]) if row and row[0] else None
            if dt is not None and dt > lower_bound:
                lower_bound = dt

        if tf == "M15":
            boundaries = [hour_start + timedelta(minutes=m) for m in (0, 15, 30, 45)]
        elif tf == "H1":
            boundaries = [hour_start]
        else:  # H4
            boundaries = [hour_start] if hour_start.hour % 4 == 0 else []

        return sum(1 for boundary in boundaries if lower_bound <= boundary <= now_dt)

    def record_scanner_telemetry(
        self,
        candidate_id: str,
        symbol: str,
        timeframe: str,
        success: bool,
        error_code: Optional[str] = None,
        now_str: Optional[str] = None,
    ) -> None:
        """Registra a telemetria prospectiva de um ciclo de varredura (1h aggregation window)."""
        from backend.core.time_utils import now_utc_datetime, format_utc_str, parse_utc_timestamp

        if not now_str:
            now_dt = now_utc_datetime()
        else:
            now_dt = parse_utc_timestamp(now_str)
            if now_dt is None:
                raise ValueError(f"Invalid scanner telemetry timestamp: {now_str!r}")
        window_start = format_utc_str(now_dt.replace(minute=0, second=0, microsecond=0))
        window_end = format_utc_str(now_dt.replace(minute=59, second=59, microsecond=999999))
        ts_now = format_utc_str(now_dt)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            nominal_expected = self._expected_checks_for_window(
                candidate_id=candidate_id,
                timeframe=timeframe,
                now_dt=now_dt,
                cursor=cursor,
            )
            if nominal_expected <= 0:
                if not success:
                    return
                nominal_expected = 1
            cursor.execute(
                """
                SELECT expected_checks, successful_checks, failed_checks, last_success_at, last_failure_at, last_error_code
                FROM shadow_scanner_telemetry
                WHERE candidate_id = ? AND window_start = ? AND symbol = ? AND timeframe = ?
                """,
                (candidate_id, window_start, symbol, timeframe),
            )
            row = cursor.fetchone()

            if row:
                succ = int(row["successful_checks"] or 0)
                fail = int(row["failed_checks"] or 0)
                exp = nominal_expected
                observed_slots = succ + fail

                if success:
                    if observed_slots < nominal_expected:
                        succ += 1
                    elif fail > 0:
                        fail -= 1
                        succ += 1
                    last_succ = ts_now
                    last_fail = row["last_failure_at"]
                    err_code = None if fail == 0 else row["last_error_code"]
                else:
                    if observed_slots < nominal_expected:
                        fail += 1
                    last_succ = row["last_success_at"]
                    last_fail = ts_now
                    err_code = error_code or "SCANNER_EXCEPTION"

                cursor.execute(
                    """
                    UPDATE shadow_scanner_telemetry
                    SET expected_checks = ?, successful_checks = ?, failed_checks = ?,
                        last_success_at = ?, last_failure_at = ?, last_error_code = ?, updated_at = ?
                    WHERE candidate_id = ? AND window_start = ? AND symbol = ? AND timeframe = ?
                    """,
                    (exp, succ, fail, last_succ, last_fail, err_code, ts_now, candidate_id, window_start, symbol, timeframe),
                )
            else:
                succ = 1 if success else 0
                fail = 0 if success else 1
                exp = nominal_expected
                last_succ = ts_now if success else None
                last_fail = None if success else ts_now
                err_code = None if success else (error_code or "SCANNER_EXCEPTION")

                cursor.execute(
                    """
                    INSERT INTO shadow_scanner_telemetry (
                        candidate_id, window_start, window_end, symbol, timeframe,
                        expected_checks, successful_checks, failed_checks,
                        last_success_at, last_failure_at, last_error_code, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (candidate_id, window_start, window_end, symbol, timeframe, exp, succ, fail, last_succ, last_fail, err_code, ts_now, ts_now),
                )
            conn.commit()

    def get_shadow_telemetry(self, candidate_id: str = "hdf_dvp_exit_2r") -> Dict[str, Any]:
        """Coverage of provider-supported Shadow combinations; configured universe remains auditable."""
        from backend.services.shadow_scanner import SHADOW_ASSETS, SHADOW_TIMEFRAMES, get_asset_class

        provider_support = self.get_provider_support()
        supported_assets = [
            sym for sym in SHADOW_ASSETS
            if provider_support.get(sym, {}).get("supported", True)
        ]
        unsupported_assets = [sym for sym in SHADOW_ASSETS if sym not in supported_assets]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            combinations_telemetry = []
            tot_expected = 0
            tot_successful = 0
            tot_failed = 0
            global_last_activity: Optional[str] = None

            for sym in SHADOW_ASSETS:
                provider_supported = sym in supported_assets
                support_reason = provider_support.get(sym, {}).get("reason", "SUPPORT_UNKNOWN_ASSUME_CONFIGURED")
                for tf in SHADOW_TIMEFRAMES:
                    cursor.execute(
                        """
                        SELECT SUM(expected_checks) as sum_exp, SUM(successful_checks) as sum_succ,
                               SUM(failed_checks) as sum_fail, MAX(last_success_at) as max_succ_at,
                               MAX(last_failure_at) as max_fail_at, MAX(updated_at) as max_upd_at
                        FROM shadow_scanner_telemetry
                        WHERE candidate_id = ? AND symbol = ? AND timeframe = ?
                        """,
                        (candidate_id, sym, tf),
                    )
                    row = cursor.fetchone()
                    exp = int(row["sum_exp"] or 0)
                    succ = int(row["sum_succ"] or 0)
                    fail = int(row["sum_fail"] or 0)
                    last_succ = row["max_succ_at"] if row else None
                    last_fail = row["max_fail_at"] if row else None
                    last_act = (row["max_upd_at"] if row else None) or last_succ

                    if provider_supported:
                        if last_act and (global_last_activity is None or last_act > global_last_activity):
                            global_last_activity = last_act
                        tot_expected += exp
                        tot_successful += succ
                        tot_failed += fail

                    cov = round(succ / exp, 4) if exp > 0 else None
                    if not provider_supported:
                        health = "UNSUPPORTED_BY_PROVIDER"
                    elif exp == 0:
                        health = "UNKNOWN"
                    elif cov is not None and cov >= 0.95:
                        health = "HEALTHY"
                    elif cov is not None and cov > 0.0:
                        health = "DEGRADED"
                    else:
                        health = "UNAVAILABLE"

                    combinations_telemetry.append({
                        "symbol": sym, "asset_class": get_asset_class(sym), "timeframe": tf,
                        "provider_supported": provider_supported, "support_reason": support_reason,
                        "coverage_included": provider_supported,
                        "expected_checks": exp, "successful_checks": succ, "failed_checks": fail,
                        "coverage": cov, "last_success_at": last_succ, "last_failure_at": last_fail,
                        "health": health,
                    })

            global_cov = round(tot_successful / tot_expected, 4) if tot_expected > 0 else None
            if tot_expected == 0:
                global_health = "UNKNOWN"
            elif global_cov is not None and global_cov >= 0.95:
                global_health = "HEALTHY"
            elif global_cov is not None and global_cov > 0.0:
                global_health = "DEGRADED"
            else:
                global_health = "UNAVAILABLE"

            return {
                "candidate_id": candidate_id,
                "global": {
                    "total_combinations": len(SHADOW_ASSETS) * len(SHADOW_TIMEFRAMES),
                    "configured_combinations": len(SHADOW_ASSETS) * len(SHADOW_TIMEFRAMES),
                    "provider_supported_combinations": len(supported_assets) * len(SHADOW_TIMEFRAMES),
                    "provider_unsupported_combinations": len(unsupported_assets) * len(SHADOW_TIMEFRAMES),
                    "unsupported_symbols": unsupported_assets,
                    "expected_checks": tot_expected, "successful_checks": tot_successful,
                    "failed_checks": tot_failed, "coverage": global_cov,
                    "health": global_health, "last_activity_at": global_last_activity,
                },
                "combinations": combinations_telemetry,
            }

    def record_prospective_observation(
        self,
        candidate_id: str,
        candidate_version: str,
        parameter_hash: str,
        symbol: str,
        asset_class: str,
        timeframe: str,
        window_time: str,
        observational_status: str,
        evidence_state: str,
        reason_codes: List[str],
        sample_size: int,
        scanner_coverage: Optional[float],
        expectancy_r: Optional[float],
        win_rate: Optional[float],
        profit_factor: Optional[float],
        max_drawdown: Optional[float],
        quality_context: str,
        degraded_flag: bool = False,
        contradictions: Optional[List[str]] = None,
        observed_at: Optional[str] = None,
    ) -> bool:
        """Persiste uma observação prospectiva de forma idempotente e rastreia transições de estado de evidência."""
        from backend.core.time_utils import now_utc_str
        ts_now = observed_at or now_utc_str()
        obs_id = f"obs_{candidate_id}_{symbol}_{timeframe}_{window_time.replace(':', '-').replace(' ', '_')}"
        reason_codes_json = json.dumps(reason_codes)
        contradictions_json = json.dumps(contradictions or [])

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Verificar última transição de estado gravada para esta combinação
            cursor.execute(
                """SELECT to_state FROM shadow_evidence_transitions
                   WHERE candidate_id = ? AND symbol = ? AND timeframe = ?
                   ORDER BY id DESC LIMIT 1""",
                (candidate_id, symbol, timeframe),
            )
            row = cursor.fetchone()
            last_state = row[0] if row else None

            if last_state != evidence_state:
                cursor.execute(
                    """INSERT INTO shadow_evidence_transitions
                       (candidate_id, symbol, timeframe, from_state, to_state, reason_code, transitioned_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate_id,
                        symbol,
                        timeframe,
                        last_state or "UNINITIALIZED",
                        evidence_state,
                        reason_codes[0] if reason_codes else "STATE_CHANGE",
                        ts_now,
                    ),
                )

            # Gravar observação de forma idempotente (INSERT OR IGNORE por UNIQUE candidate_id, symbol, timeframe, window_time)
            cursor.execute(
                """INSERT OR IGNORE INTO shadow_prospective_observations
                   (observation_id, candidate_id, candidate_version, parameter_hash, symbol, asset_class,
                    timeframe, window_time, observational_status, evidence_state, reason_codes_json,
                    sample_size, scanner_coverage, expectancy_r, win_rate, profit_factor, max_drawdown,
                    quality_context, degraded_flag, contradictions_json, observed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    obs_id,
                    candidate_id,
                    candidate_version,
                    parameter_hash,
                    symbol,
                    asset_class,
                    timeframe,
                    window_time,
                    observational_status,
                    evidence_state,
                    reason_codes_json,
                    sample_size,
                    scanner_coverage,
                    expectancy_r,
                    win_rate,
                    profit_factor,
                    max_drawdown,
                    quality_context,
                    1 if degraded_flag else 0,
                    contradictions_json,
                    ts_now,
                ),
            )
            inserted = cursor.rowcount > 0
            conn.commit()
            return inserted

    def get_prospective_observations(
        self,
        candidate_id: str = "hdf_dvp_exit_2r",
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retorna histórico de observações prospectivas registradas."""
        query = "SELECT * FROM shadow_prospective_observations WHERE candidate_id = ?"
        params: List[Any] = [candidate_id]

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)

        query += " ORDER BY observed_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                result.append({
                    "observation_id": r["observation_id"],
                    "candidate_id": r["candidate_id"],
                    "candidate_version": r["candidate_version"],
                    "parameter_hash": r["parameter_hash"],
                    "symbol": r["symbol"],
                    "asset_class": r["asset_class"],
                    "timeframe": r["timeframe"],
                    "window_time": r["window_time"],
                    "observational_status": r["observational_status"],
                    "evidence_state": r["evidence_state"],
                    "reason_codes": json.loads(r["reason_codes_json"]) if r["reason_codes_json"] else [],
                    "sample_size": r["sample_size"],
                    "scanner_coverage": r["scanner_coverage"],
                    "expectancy_r": r["expectancy_r"],
                    "win_rate": r["win_rate"],
                    "profit_factor": r["profit_factor"],
                    "max_drawdown": r["max_drawdown"],
                    "quality_context": r["quality_context"],
                    "degraded_flag": bool(r["degraded_flag"]),
                    "contradictions": json.loads(r["contradictions_json"]) if r["contradictions_json"] else [],
                    "observed_at": r["observed_at"],
                })
            return result

    def get_evidence_transitions(
        self,
        candidate_id: str = "hdf_dvp_exit_2r",
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retorna o histórico de transições de evidência registradas."""
        query = "SELECT * FROM shadow_evidence_transitions WHERE candidate_id = ?"
        params: List[Any] = [candidate_id]

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "candidate_id": r["candidate_id"],
                    "symbol": r["symbol"],
                    "timeframe": r["timeframe"],
                    "from_state": r["from_state"],
                    "to_state": r["to_state"],
                    "reason_code": r["reason_code"],
                    "transitioned_at": r["transitioned_at"],
                }
                for r in rows
            ]

    def save_hdf_evidence(self, ev: HDFEvidence) -> bool:
        """Persiste ou atualiza uma HDFEvidence na tabela shadow_hdf_evidence."""
        from backend.core.time_utils import now_utc_str
        now_str = now_utc_str()
        reasons_json = json.dumps(ev.reason_codes or [])
        source_val = getattr(ev, "source", "LIVE_PROSPECTIVE") or "LIVE_PROSPECTIVE"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO shadow_hdf_evidence (
                    evidence_id, symbol, timeframe, asset_class, direction,
                    pivot_1_time, pivot_1_price, pivot_1_rsi,
                    pivot_2_time, pivot_2_price, pivot_2_rsi,
                    divergence_confirmed, relative_volume, volume_pass,
                    pattern_type, pattern_pass, pattern_policy,
                    variant_stage, candidate_created, armed, activated,
                    event_id, reason_codes_json, source, is_test, detected_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, pivot_2_time, direction) DO NOTHING
                """,
                (
                    ev.evidence_id, ev.symbol, ev.timeframe, ev.asset_class, ev.direction,
                    ev.pivot_1_time, ev.pivot_1_price, ev.pivot_1_rsi,
                    ev.pivot_2_time, ev.pivot_2_price, ev.pivot_2_rsi,
                    1 if ev.divergence_confirmed else 0, ev.relative_volume, 1 if ev.volume_pass else 0,
                    ev.pattern_type, 1 if ev.pattern_pass else 0, ev.pattern_policy,
                    ev.variant_stage, 1 if ev.candidate_created else 0, 1 if ev.armed else 0, 1 if ev.activated else 0,
                    ev.event_id, reasons_json, source_val, 1 if ev.is_test else 0,
                    ev.detected_at or now_str, ev.created_at or now_str,
                ),
            )
            conn.commit()
            return True

    def _row_to_evidence(self, r: sqlite3.Row) -> HDFEvidence:
        source_val = r["source"] if "source" in r.keys() else "LIVE_PROSPECTIVE"
        return HDFEvidence(
            evidence_id=r["evidence_id"],
            symbol=r["symbol"],
            timeframe=r["timeframe"],
            asset_class=r["asset_class"],
            direction=r["direction"],
            pivot_1_time=r["pivot_1_time"],
            pivot_1_price=float(r["pivot_1_price"]),
            pivot_1_rsi=float(r["pivot_1_rsi"]),
            pivot_2_time=r["pivot_2_time"],
            pivot_2_price=float(r["pivot_2_price"]),
            pivot_2_rsi=float(r["pivot_2_rsi"]),
            divergence_confirmed=bool(r["divergence_confirmed"]),
            relative_volume=float(r["relative_volume"]),
            volume_pass=bool(r["volume_pass"]),
            pattern_type=r["pattern_type"],
            pattern_pass=bool(r["pattern_pass"]),
            pattern_policy=r["pattern_policy"],
            variant_stage=r["variant_stage"],
            candidate_created=bool(r["candidate_created"]),
            armed=bool(r["armed"]),
            activated=bool(r["activated"]),
            event_id=r["event_id"],
            reason_codes=json.loads(r["reason_codes_json"]) if r["reason_codes_json"] else [],
            source=source_val,
            is_test=bool(r["is_test"]),
            detected_at=r["detected_at"],
            created_at=r["created_at"],
        )

    def list_hdf_evidence(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        source: Optional[str] = "LIVE_PROSPECTIVE",
        is_test: bool = False,
        include_non_live: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[HDFEvidence]:
        """Retorna a lista de HDFEvidence filtrada por proveniência e parâmetros."""
        if include_non_live:
            query = "SELECT * FROM shadow_hdf_evidence WHERE 1=1"
            params: List[Any] = []
        elif source:
            query = "SELECT * FROM shadow_hdf_evidence WHERE source = ? AND is_test = ?"
            params = [source, 1 if is_test else 0]
        else:
            query = "SELECT * FROM shadow_hdf_evidence WHERE is_test = ?"
            params = [1 if is_test else 0]

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_evidence(r) for r in rows]

    def get_hdf_evidence(self, evidence_id: str) -> Optional[HDFEvidence]:
        """Retorna uma HDFEvidence específica pelo evidence_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shadow_hdf_evidence WHERE evidence_id = ?", (evidence_id,))
            r = cursor.fetchone()
            return self._row_to_evidence(r) if r else None

    def get_funnel_telemetry(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Métrica agregada e real do funil HDF calculada a partir dos dados do banco."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            ev_where = "WHERE is_test = 0"
            ev_params: List[Any] = []
            evt_where = "WHERE 1=1"
            evt_params: List[Any] = []

            if symbol:
                ev_where += " AND symbol = ?"
                ev_params.append(symbol)
                evt_where += " AND symbol = ?"
                evt_params.append(symbol)
            if timeframe:
                ev_where += " AND timeframe = ?"
                ev_params.append(timeframe)
                evt_where += " AND timeframe = ?"
                evt_params.append(timeframe)

            cursor.execute(f"SELECT COUNT(*) FROM shadow_hdf_evidence {ev_where}", ev_params)
            hdf_d = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM shadow_hdf_evidence {ev_where} AND volume_pass = 1", ev_params)
            hdf_dv = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM shadow_hdf_evidence {ev_where} AND pattern_pass = 1", ev_params)
            hdf_dp = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM shadow_hdf_evidence {ev_where} AND volume_pass = 1 AND pattern_pass = 1", ev_params)
            hdf_dvp = cursor.fetchone()[0]

            live_cands = self._get_live_candidates(cursor, symbol=symbol, timeframe=timeframe)
            candidates = len(live_cands)

            cursor.execute(f"SELECT COUNT(*) FROM shadow_events {evt_where} AND event_id NOT LIKE 'test_%'", evt_params)
            real_events_count = cursor.fetchone()[0]

            cursor.execute(f"SELECT current_state, COUNT(*) FROM shadow_events {evt_where} AND event_id NOT LIKE 'test_%' GROUP BY current_state", evt_params)
            state_counts = dict(cursor.fetchall())

            return {
                "symbol": symbol or "ALL",
                "timeframe": timeframe or "ALL",
                "pivots": hdf_d * 2,
                "hdf_d": hdf_d,
                "hdf_dv": hdf_dv,
                "hdf_dp": hdf_dp,
                "hdf_dvp": hdf_dvp,
                "candidates": candidates,
                "armed": state_counts.get("ARMED", 0),
                "activated": state_counts.get("ACTIVATED", 0),
                "expired": state_counts.get("EXPIRED", 0),
                "invalidated": state_counts.get("INVALIDATED_BEFORE_ACTIVATION", 0),
                "target_2r": state_counts.get("TARGET_2R", 0),
                "stopped": state_counts.get("STOPPED", 0),
                "total_real_events": real_events_count,
            }

    def upsert_fibonacci_telemetry(self, record: Dict[str, Any]) -> bool:
        """Insert immutable decision snapshot; update only post-decision observation fields."""
        record = dict(record)
        record.setdefault("evidence_snapshot_json", "{}")
        columns = [
            "telemetry_id", "research_scope", "candidate_id", "occurrence_id",
            "symbol", "timeframe", "direction", "mode", "role", "policy_id",
            "decision_time", "decision_status", "decision_reason",
            "anchor_a_time", "anchor_a_price", "anchor_a_confirmed_at",
            "anchor_b_time", "anchor_b_price", "anchor_b_confirmed_at",
            "levels_json", "matched_levels_json", "evidence_snapshot_json", "activated", "activation_level",
            "entry_time", "entry_price", "stop_price", "target_outcomes_json",
            "last_observed_candle", "source", "is_test", "created_at", "updated_at",
        ]
        values = [record.get(col) for col in columns]
        placeholders = ",".join("?" for _ in columns)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO shadow_fibonacci_telemetry ({','.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(telemetry_id) DO UPDATE SET
                    activated = excluded.activated,
                    entry_time = excluded.entry_time,
                    entry_price = excluded.entry_price,
                    stop_price = excluded.stop_price,
                    target_outcomes_json = excluded.target_outcomes_json,
                    last_observed_candle = excluded.last_observed_candle,
                    updated_at = excluded.updated_at
                """,
                values,
            )
            conn.commit()
        return True

    def has_fibonacci_telemetry(
        self,
        telemetry_id: str,
        *,
        source: Optional[str] = None,
        is_test: Optional[bool] = None,
    ) -> bool:
        query = "SELECT 1 FROM shadow_fibonacci_telemetry WHERE telemetry_id = ?"
        params: List[Any] = [telemetry_id]
        if source is not None:
            query += " AND source = ?"
            params.append(source)
        if is_test is not None:
            query += " AND is_test = ?"
            params.append(1 if is_test else 0)
        query += " LIMIT 1"
        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone() is not None

    def get_fibonacci_telemetry(
        self,
        *,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        mode: Optional[str] = None,
        source: Optional[str] = "LIVE_PROSPECTIVE",
        is_test: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM shadow_fibonacci_telemetry WHERE 1=1"
        params: List[Any] = []
        if source is not None:
            query += " AND source = ? AND is_test = ?"
            params.extend([source, 1 if is_test else 0])
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)
        if mode:
            query += " AND mode = ?"
            params.append(mode)
        query += " ORDER BY decision_time DESC, mode ASC LIMIT ?"
        params.append(int(limit))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
