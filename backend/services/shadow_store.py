from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
import numpy as np

from backend.domain.shadow_models import (
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
                error_message TEXT
            )
            """)

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
                key, candidate_id, symbol, timeframe, enabled, last_processed_candle, last_scan_at, scanner_status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    key, state.candidate_id, state.symbol, state.timeframe, 1 if state.enabled else 0,
                    state.last_processed_candle, state.last_scan_at, state.scanner_status, state.error_message,
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
                    last_scan_at=r["last_scan_at"], scanner_status=r["scanner_status"], error_message=r["error_message"],
                )
            return None

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
        from datetime import datetime
        from backend.core.time_utils import now_utc_datetime, format_utc_str

        now_dt = now_utc_datetime() if not now_str else datetime.fromisoformat(now_str.replace("Z", "+00:00"))
        window_start = format_utc_str(now_dt.replace(minute=0, second=0, microsecond=0))
        window_end = format_utc_str(now_dt.replace(minute=59, second=59, microsecond=999999))
        ts_now = format_utc_str(now_dt)

        nominal_expected = 4 if timeframe.upper() == "M15" else 1

        with self._get_connection() as conn:
            cursor = conn.cursor()
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
                succ = row["successful_checks"] + (1 if success else 0)
                fail = row["failed_checks"] + (0 if success else 1)
                exp = max(nominal_expected, succ + fail)
                last_succ = ts_now if success else row["last_success_at"]
                last_fail = row["last_failure_at"] if success else ts_now
                err_code = row["last_error_code"] if success else (error_code or "SCANNER_EXCEPTION")

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
                exp = max(nominal_expected, succ + fail)
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
        """Retorna o relatório completo de telemetria e cobertura de varredura do Shadow Mode."""
        from backend.services.shadow_scanner import SHADOW_ASSETS, SHADOW_TIMEFRAMES, get_asset_class

        with self._get_connection() as conn:
            cursor = conn.cursor()

            combinations_telemetry = []
            tot_expected = 0
            tot_successful = 0
            tot_failed = 0
            global_last_activity: Optional[str] = None

            for sym in SHADOW_ASSETS:
                for tf in SHADOW_TIMEFRAMES:
                    cursor.execute(
                        """
                        SELECT SUM(expected_checks) as sum_exp,
                               SUM(successful_checks) as sum_succ,
                               SUM(failed_checks) as sum_fail,
                               MAX(last_success_at) as max_succ_at,
                               MAX(last_failure_at) as max_fail_at,
                               MAX(updated_at) as max_upd_at
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

                    if last_act and (global_last_activity is None or last_act > global_last_activity):
                        global_last_activity = last_act

                    tot_expected += exp
                    tot_successful += succ
                    tot_failed += fail

                    cov = round(succ / exp, 4) if exp > 0 else None

                    if exp == 0:
                        health = "UNKNOWN"
                    elif cov is not None and cov >= 0.95:
                        health = "HEALTHY"
                    elif cov is not None and cov > 0.0:
                        health = "DEGRADED"
                    else:
                        health = "UNAVAILABLE"

                    combinations_telemetry.append({
                        "symbol": sym,
                        "asset_class": get_asset_class(sym),
                        "timeframe": tf,
                        "expected_checks": exp,
                        "successful_checks": succ,
                        "failed_checks": fail,
                        "coverage": cov,
                        "last_success_at": last_succ,
                        "last_failure_at": last_fail,
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
                    "total_combinations": 39,
                    "expected_checks": tot_expected,
                    "successful_checks": tot_successful,
                    "failed_checks": tot_failed,
                    "coverage": global_cov,
                    "health": global_health,
                    "last_activity_at": global_last_activity,
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
