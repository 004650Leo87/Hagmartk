"""Hagmartk Prospective Observation & Accumulation Engine V1 (Fase 4F).

Motor de observação continuada e acúmulo prospectivo confiável.
Responsável por:
1. Gravação de observações prospectivas sem look-ahead bias
2. Idempotência por (candidate_id, symbol, timeframe, window_time)
3. Rastreamento de transições de estado de evidência ao longo do tempo
4. Consolidação da saúde da observação (39 combinações)
5. Acompanhamento do progresso do acúmulo da amostra
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.core.time_utils import now_utc_str
from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.services.shadow_decision_evidence import ShadowDecisionEvidenceEngine
from backend.services.shadow_scanner import SHADOW_ASSETS, SHADOW_TIMEFRAMES, get_asset_class
from backend.services.shadow_store import ShadowStoreRepository


class ShadowObservationEngine:
    """Motor de acúmulo e acompanhamento prospectivo continuado."""

    def __init__(
        self,
        store: Optional[ShadowStoreRepository] = None,
        decision_engine: Optional[ShadowDecisionEvidenceEngine] = None,
    ) -> None:
        self.store = store or ShadowStoreRepository()
        self.decision_engine = decision_engine or ShadowDecisionEvidenceEngine(store=self.store)

    def record_observation_cycle(
        self,
        symbol: str,
        timeframe: str,
        window_time: str,
        candidate_id: str = "hdf_dvp_exit_2r",
        observed_at: Optional[str] = None,
    ) -> bool:
        """Avalia a Decision Layer e grava a observação prospectiva de forma idempotente."""
        evidence_obj = self.decision_engine.evaluate_evidence(candidate_id=candidate_id)
        asset_class = get_asset_class(symbol)
        param_hash = HDF_ROBUST_CANDIDATE_V1.compute_parameter_hash()

        degraded = (
            evidence_obj.data_quality.get("scanner_coverage") is not None
            and evidence_obj.data_quality.get("scanner_coverage") < 0.95
        )

        return self.store.record_prospective_observation(
            candidate_id=candidate_id,
            candidate_version=HDF_ROBUST_CANDIDATE_V1.candidate_version,
            parameter_hash=param_hash,
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            window_time=window_time,
            observational_status=evidence_obj.observational_status,
            evidence_state=evidence_obj.evidence_state,
            reason_codes=evidence_obj.reason_codes,
            sample_size=evidence_obj.sample.get("size", 0),
            scanner_coverage=evidence_obj.data_quality.get("scanner_coverage"),
            expectancy_r=evidence_obj.performance.get("expectancy_r"),
            win_rate=evidence_obj.performance.get("win_rate_pct"),
            profit_factor=evidence_obj.performance.get("profit_factor"),
            max_drawdown=evidence_obj.performance.get("max_drawdown_r"),
            quality_context=evidence_obj.data_quality.get("state", "UNAVAILABLE"),
            degraded_flag=degraded,
            contradictions=evidence_obj.contradictions,
            observed_at=observed_at,
        )

    def get_observation_health(self, candidate_id: str = "hdf_dvp_exit_2r") -> Dict[str, Any]:
        """Retorna o resumo consolidado da saúde da observação prospectiva (39 combinações)."""
        telemetry = self.store.get_shadow_telemetry(candidate_id=candidate_id)
        glob_telem = telemetry.get("global", {})
        comb_telem = telemetry.get("combinations", [])

        obs_list = self.store.get_prospective_observations(candidate_id=candidate_id, limit=500)

        obs_symbols_tfs = set((o["symbol"], o["timeframe"]) for o in obs_list)
        observed_count = len(obs_symbols_tfs)

        healthy_cnt = sum(1 for c in comb_telem if c.get("health") == "HEALTHY")
        degraded_cnt = sum(1 for c in comb_telem if c.get("health") == "DEGRADED")
        insufficient_cnt = sum(1 for c in comb_telem if c.get("health") in ("UNKNOWN", "UNAVAILABLE"))

        newest_ts = None
        oldest_ts = None
        if obs_list:
            sorted_obs = sorted(obs_list, key=lambda x: x["observed_at"])
            oldest_ts = sorted_obs[0]["observed_at"]
            newest_ts = sorted_obs[-1]["observed_at"]

        return {
            "candidate_id": candidate_id,
            "total_universe_combinations": 39,
            "observed_combinations": observed_count,
            "healthy_combinations": healthy_cnt,
            "degraded_combinations": degraded_cnt,
            "insufficient_data_combinations": insufficient_cnt,
            "error_combinations": glob_telem.get("failed_checks", 0),
            "global_coverage_pct": (glob_telem.get("coverage") * 100.0) if glob_telem.get("coverage") is not None else None,
            "global_health": glob_telem.get("health", "UNKNOWN"),
            "oldest_observation_at": oldest_ts,
            "newest_observation_at": newest_ts,
        }

    def get_accumulation_progress(self, candidate_id: str = "hdf_dvp_exit_2r") -> Dict[str, Any]:
        """Retorna o detalhamento do acúmulo de amostras por combinação (SYMBOL x TIMEFRAME)."""
        all_events = self.store.list_history_events()
        all_obs = self.store.get_prospective_observations(candidate_id=candidate_id, limit=1000)
        telemetry = self.store.get_shadow_telemetry(candidate_id=candidate_id)
        comb_telem_map = {(c["symbol"], c["timeframe"]): c for c in telemetry.get("combinations", [])}

        combinations_progress = []

        for sym in SHADOW_ASSETS:
            for tf in SHADOW_TIMEFRAMES:
                pair_events = [e for e in all_events if e.symbol == sym and e.timeframe == tf]
                resolved_events = [e for e in pair_events if e.current_state in ("TARGET_2R", "STOPPED")]
                pending_events = [e for e in pair_events if e.current_state in ("ARMED", "ACTIVATED")]

                pair_obs = [o for o in all_obs if o["symbol"] == sym and o["timeframe"] == tf]
                obs_cnt = len(pair_obs)

                first_obs = pair_obs[-1]["observed_at"] if pair_obs else None
                latest_obs = pair_obs[0]["observed_at"] if pair_obs else None

                current_evidence = pair_obs[0]["evidence_state"] if pair_obs else "INSUFFICIENT_EVIDENCE"

                telem_info = comb_telem_map.get((sym, tf), {})
                cov = telem_info.get("coverage", None)

                combinations_progress.append({
                    "symbol": sym,
                    "asset_class": get_asset_class(sym),
                    "timeframe": tf,
                    "observations_count": obs_cnt,
                    "hdf_events_count": len(pair_events),
                    "resolved_trades": len(resolved_events),
                    "pending_setups": len(pending_events),
                    "sample_size": len(resolved_events),
                    "coverage_pct": (cov * 100.0) if cov is not None else None,
                    "first_observation_at": first_obs,
                    "latest_observation_at": latest_obs,
                    "current_evidence_state": current_evidence,
                    "health": telem_info.get("health", "UNKNOWN"),
                })

        return {
            "candidate_id": candidate_id,
            "total_combinations": 39,
            "combinations": combinations_progress,
        }

    def get_combination_drilldown(
        self, symbol: str, timeframe: str, candidate_id: str = "hdf_dvp_exit_2r"
    ) -> Dict[str, Any]:
        """Retorna o payload completo de drill-down para uma combinação específica."""
        obs_history = self.store.get_prospective_observations(
            candidate_id=candidate_id, symbol=symbol, timeframe=timeframe, limit=50
        )
        transitions = self.store.get_evidence_transitions(
            candidate_id=candidate_id, symbol=symbol, timeframe=timeframe, limit=50
        )

        all_events = self.store.list_history_events()
        pair_events = [e for e in all_events if e.symbol == symbol and e.timeframe == timeframe]

        latest_obs = obs_history[0] if obs_history else None

        return {
            "candidate_id": candidate_id,
            "symbol": symbol,
            "asset_class": get_asset_class(symbol),
            "timeframe": timeframe,
            "latest_observation": latest_obs,
            "observations_count": len(obs_history),
            "events_count": len(pair_events),
            "events": [
                {
                    "event_id": e.event_id,
                    "direction": e.direction,
                    "current_state": e.current_state,
                    "confluence_time": e.confluence_time,
                    "activated_at": e.activated_at,
                    "initial_stop": e.initial_stop,
                    "target_2R": e.target_2R,
                }
                for e in pair_events
            ],
            "observation_history": obs_history,
            "evidence_transitions": transitions,
        }
