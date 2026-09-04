from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH, HDF_ROBUST_CANDIDATE_V1
from backend.services.alert_engine import InternalAlertEngine
from backend.services.shadow_scanner import SHADOW_ASSETS, SHADOW_TIMEFRAMES, ShadowScannerManager
from backend.services.shadow_store import ShadowStoreRepository
from backend.services.fibonacci_prospective_telemetry import FibonacciProspectiveTelemetryEngine
from backend.strategies.hdf.exit_policy_provenance import get_exit_policy_provenance

from backend.services.shadow_performance import ShadowPerformanceEngine
from backend.services.shadow_statistical_validation import ShadowStatisticalValidationEngine

router = APIRouter(prefix="/api/shadow", tags=["Shadow Mode"])

_store = ShadowStoreRepository()
_scanner = ShadowScannerManager(store=_store)
_performance_engine = ShadowPerformanceEngine(store=_store)
from backend.services.shadow_intelligence import ShadowIntelligenceEngine
from backend.services.shadow_decision_evidence import ShadowDecisionEvidenceEngine
from backend.services.shadow_observation_engine import ShadowObservationEngine

_stat_engine = ShadowStatisticalValidationEngine(perf_engine=_performance_engine)
_intel_engine = ShadowIntelligenceEngine(store=_store, perf_engine=_performance_engine, stat_engine=_stat_engine)
_evidence_engine = ShadowDecisionEvidenceEngine(store=_store, intel_engine=_intel_engine)
_obs_engine = ShadowObservationEngine(store=_store, decision_engine=_evidence_engine)
_fib_engine = FibonacciProspectiveTelemetryEngine(store=_store)


@router.get("/forward-validation")
def get_shadow_forward_validation(candidate_id: str = Query("hdf_dvp_exit_2r")) -> Dict[str, Any]:
    """Retorna o snapshot completo de validação prospectiva do Shadow Mode."""
    snapshot = _performance_engine.build_snapshot(candidate_id=candidate_id)
    return snapshot.to_dict()


@router.get("/statistical-validation")
def get_shadow_statistical_validation(candidate_id: str = Query("hdf_dvp_exit_2r")) -> Dict[str, Any]:
    """Retorna o snapshot completo de inferência estatística prospectiva do Shadow Mode (READ-ONLY)."""
    snapshot = _stat_engine.build_validation_snapshot(candidate_id=candidate_id)
    return snapshot.to_dict()


@router.get("/telemetry")
def get_shadow_telemetry(candidate_id: str = Query("hdf_dvp_exit_2r")) -> Dict[str, Any]:
    """Retorna o relatório completo de observabilidade e telemetria operacional do Shadow Mode (READ-ONLY)."""
    return _store.get_shadow_telemetry(candidate_id=candidate_id)


@router.get("/fibonacci-research")
def get_fibonacci_research(candidate_id: str = Query("hdf_dvp_exit_2r")) -> Dict[str, Any]:
    """Retorna o resumo prospectivo de pesquisa Fibonacci (READ-ONLY / NO PROMOTION)."""
    return _fib_engine.build_research_summary(candidate_id=candidate_id)


@router.get("/intelligence")
def get_shadow_intelligence(candidate_id: str = Query("hdf_dvp_exit_2r")) -> Dict[str, Any]:
    """Retorna o relatório consolidado das 9 camadas de Inteligência e Validação Prospectiva (READ-ONLY)."""
    snapshot = _intel_engine.build_intelligence_snapshot(candidate_id=candidate_id)
    return snapshot.to_dict()


@router.get("/evidence")
def get_shadow_evidence(candidate_id: str = Query("hdf_dvp_exit_2r")) -> Dict[str, Any]:
    """Retorna a classificação determinística da Decision & Evidence Layer V1 (READ-ONLY)."""
    evidence_obj = _evidence_engine.evaluate_evidence(candidate_id=candidate_id)
    return evidence_obj.to_dict()


@router.get("/evidence/recent")
def list_recent_hdf_evidences(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    include_non_live: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Retorna as HDFEvidences matemáticas confirmadas (READ-ONLY). Retorna apenas LIVE_PROSPECTIVE por padrão."""
    evidences = _store.list_hdf_evidence(
        symbol=symbol,
        timeframe=timeframe,
        source="LIVE_PROSPECTIVE",
        is_test=False,
        include_non_live=include_non_live,
        limit=limit,
        offset=offset,
    )
    return {
        "symbol": symbol or "ALL",
        "timeframe": timeframe or "ALL",
        "include_non_live": include_non_live,
        "total": len(evidences),
        "evidences": [ev.__dict__ for ev in evidences],
    }


@router.get("/evidence/by-symbol/{symbol}")
def list_hdf_evidences_by_symbol(
    symbol: str,
    timeframe: Optional[str] = Query(None),
    include_non_live: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Retorna as HDFEvidences LIVE_PROSPECTIVE para renderização visual no gráfico (READ-ONLY)."""
    symbol = symbol.strip().upper()
    evidences = _store.list_hdf_evidence(
        symbol=symbol,
        timeframe=timeframe,
        source="LIVE_PROSPECTIVE",
        is_test=False,
        include_non_live=include_non_live,
        limit=limit,
        offset=0,
    )
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "include_non_live": include_non_live,
        "evidences": [ev.__dict__ for ev in evidences],
    }


@router.get("/evidence/detail/{evidence_id}")
def get_hdf_evidence_by_id(evidence_id: str) -> Dict[str, Any]:
    """Retorna os detalhes cirúrgicos de uma HDFEvidence específica (READ-ONLY)."""
    ev = _store.get_hdf_evidence(evidence_id)
    if not ev:
        raise HTTPException(status_code=404, detail=f"Evidência HDF '{evidence_id}' não encontrada.")
    return ev.__dict__


@router.get("/funnel")
def get_hdf_funnel_telemetry(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Retorna métricas determinísticas e reais do funil HDF (Pivôs, D, DV, DP, DVP, Candidate, Armed, Activated)."""
    return _store.get_funnel_telemetry(symbol=symbol, timeframe=timeframe)


@router.get("/coverage")
def get_hdf_scanner_coverage() -> Dict[str, Any]:
    """Retorna a cobertura operacional de escaneamento do universo 39/39 com auditoria de XAUUSD."""
    from backend.services.shadow_scanner import SHADOW_ASSETS, SHADOW_TIMEFRAMES
    from backend.core.time_utils import now_utc_str, parse_utc_timestamp
    
    combinations = []
    xauusd_coverage = {}
    active_count = 0
    recent_count = 0
    stale_count = 0
    error_count = 0
    now_dt = parse_utc_timestamp(now_utc_str())

    for sym in SHADOW_ASSETS:
        for tf in SHADOW_TIMEFRAMES:
            st = _store.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, sym, tf)
            status_val = st.scanner_status if st else "RUNNING"
            last_scan = st.last_scan_at if st else ""
            
            is_active = status_val in ("RUNNING", "WAITING_NEW_CANDLE")
            if is_active:
                active_count += 1
            if status_val == "ERROR":
                error_count += 1

            is_recent = False
            if last_scan and now_dt:
                dt_scan = parse_utc_timestamp(last_scan)
                if dt_scan and (now_dt - dt_scan).total_seconds() < 900:  # 15 min
                    is_recent = True
                    recent_count += 1
                else:
                    stale_count += 1
            else:
                stale_count += 1

            item = {
                "symbol": sym,
                "timeframe": tf,
                "enabled": st.enabled if st else True,
                "status": status_val,
                "last_processed_candle": st.last_processed_candle if st else "",
                "last_scan_at": last_scan,
                "is_recent": is_recent,
                "error_message": st.error_message if st else "",
            }
            combinations.append(item)
            if sym == "XAUUSD":
                xauusd_coverage[tf] = item

    return {
        "registered": len(combinations),
        "active": active_count,
        "recently_scanned": recent_count,
        "stale": stale_count,
        "errors": error_count,
        "xauusd": xauusd_coverage,
        "combinations": combinations,
    }


@router.get("/observation/health")
def get_shadow_observation_health(candidate_id: str = Query("hdf_dvp_exit_2r")) -> Dict[str, Any]:
    """Retorna a saúde agregada da observação prospectiva (39 combinações, READ-ONLY)."""
    return _obs_engine.get_observation_health(candidate_id=candidate_id)


@router.get("/observation/progress")
def get_shadow_observation_progress(candidate_id: str = Query("hdf_dvp_exit_2r")) -> Dict[str, Any]:
    """Retorna o progresso do acúmulo da amostra prospectiva por combinação (READ-ONLY)."""
    return _obs_engine.get_accumulation_progress(candidate_id=candidate_id)


@router.get("/observation/history")
def get_shadow_observation_history(
    candidate_id: str = Query("hdf_dvp_exit_2r"),
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """Retorna o histórico de observações e transições de evidência gravadas (READ-ONLY)."""
    observations = _store.get_prospective_observations(
        candidate_id=candidate_id, symbol=symbol, timeframe=timeframe, limit=limit
    )
    transitions = _store.get_evidence_transitions(
        candidate_id=candidate_id, symbol=symbol, timeframe=timeframe, limit=limit
    )
    return {
        "candidate_id": candidate_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "observations": observations,
        "transitions": transitions,
    }


@router.get("/observation/{symbol}/{timeframe}")
def get_shadow_observation_drilldown(
    symbol: str,
    timeframe: str,
    candidate_id: str = Query("hdf_dvp_exit_2r"),
) -> Dict[str, Any]:
    """Retorna o drill-down detalhado de observação prospectiva para um par específico (READ-ONLY)."""
    return _obs_engine.get_combination_drilldown(
        symbol=symbol.upper(), timeframe=timeframe.upper(), candidate_id=candidate_id
    )


@router.get("/status")
def get_shadow_status() -> Dict[str, Any]:
    """Retorna o status geral do motor de monitoramento Shadow Mode."""
    stats = _store.get_shadow_statistics(started_at=_scanner.shadow_started_at)
    return {
        "status": "online",
        "mode": "SHADOW",
        "enabled": _scanner.enabled,
        "started_at": _scanner.shadow_started_at,
        "monitored_combinations": len(SHADOW_ASSETS) * len(SHADOW_TIMEFRAMES),
        "total_events": stats.total_events_detected,
        "active_events": stats.open_count + stats.armed_count,
        "external_publishing": "DISABLED",
        "broker_trading": "DISABLED",
    }


@router.get("/candidates")
def list_shadow_candidates() -> List[Dict[str, Any]]:
    """Retorna a lista de candidatos congelados disponíveis para o Shadow Mode (especificação imutável)."""
    cand = HDF_ROBUST_CANDIDATE_V1
    return [
        {
            "candidate_id": cand.candidate_id,
            "candidate_version": cand.candidate_version,
            "display_name": cand.display_name,
            "strategy_id": cand.strategy_id,
            "variant": cand.variant,
            "exit_policy": cand.exit_policy,
            "exit_policy_provenance": get_exit_policy_provenance(cand.exit_policy).to_dict(),
            "research_status": cand.research_status,
            "parameter_hash": HDF_CANDIDATE_V1_PARAMETER_HASH,
            "source_commit": cand.source_commit,
            "enabled": _scanner.enabled,
            "read_only_parameters": {
                "rsi_method": cand.rsi_method,
                "rsi_period": cand.rsi_period,
                "pivot_left": cand.pivot_left,
                "pivot_right": cand.pivot_right,
                "min_bars_between_pivots": cand.min_bars_between_pivots,
                "max_bars_between_pivots": cand.max_bars_between_pivots,
                "volume_min_relative": cand.volume_min_relative,
                "activation_policy": cand.activation_policy,
                "max_activation_bars": cand.max_activation_bars,
                "execution_buffer": cand.execution_buffer,
                "stop_buffer": cand.stop_buffer,
                "pattern_association_policy": cand.pattern_association_policy,
                "volume_observation_policy": cand.volume_observation_policy,
                "fibonacci_status": cand.fibonacci_status,
                "target_r": cand.target_r,
                "intrabar_policy": cand.intrabar_policy,
            },
            "limitations": list(cand.limitations),
        }
    ]


@router.post("/{candidate_id}/enable")
def enable_shadow_candidate(candidate_id: str) -> Dict[str, Any]:
    """Ativa o scanner prospectivo do candidato especifico no Shadow Mode."""
    if candidate_id != HDF_ROBUST_CANDIDATE_V1.candidate_id:
        raise HTTPException(status_code=404, detail="Candidato não encontrado no registro oficial HDF.")

    _scanner.enable_shadow()
    return {
        "candidate_id": candidate_id,
        "enabled": True,
        "started_at": _scanner.shadow_started_at,
        "message": "Shadow Mode ativado com sucesso para HDF Candidate V1.",
    }


@router.post("/{candidate_id}/disable")
def disable_shadow_candidate(candidate_id: str) -> Dict[str, Any]:
    """Desativa o scanner prospectivo do candidato no Shadow Mode."""
    if candidate_id != HDF_ROBUST_CANDIDATE_V1.candidate_id:
        raise HTTPException(status_code=404, detail="Candidato não encontrado no registro oficial HDF.")

    _scanner.disable_shadow()
    return {
        "candidate_id": candidate_id,
        "enabled": False,
        "message": "Shadow Mode desativado.",
    }


@router.get("/events")
def list_shadow_events(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista eventos prospectivos do Shadow Mode com filtros e paginação."""
    all_events = _store.list_history_events()
    filtered = []
    for evt in all_events:
        if symbol and evt.symbol != symbol:
            continue
        if timeframe and evt.timeframe != timeframe:
            continue
        if state and evt.current_state != state:
            continue
        filtered.append(InternalAlertEngine.format_market_alert(evt))
    total = len(filtered)
    page_data = filtered[offset:offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "events": page_data}


@router.get("/events/recent")
def list_recent_shadow_events(
    n: int = Query(20, ge=1, le=100),
    include_test: bool = Query(False),
    last_seen_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Retorna os N eventos mais recentes para polling do toast. Deve ficar ANTES de /events/{event_id}."""
    all_events = _store.list_history_events()
    if not include_test:
        all_events = [e for e in all_events if not e.event_id.startswith("test_") and not getattr(e, "is_test", False)]
    recent = all_events[:n]
    formatted = [InternalAlertEngine.format_market_alert(e) for e in recent]
    # Filtrar por toast-worthy states
    TOAST_STATES = {"ARMED", "ACTIVATED", "TARGET_2R", "STOPPED"}
    toast_events = [e for e in formatted if e.get("status_code") in TOAST_STATES]
    return {
        "events": formatted,
        "toast_events": toast_events,
        "total": len(all_events),
    }


@router.get("/events/{event_id}")
def get_shadow_event_detail(event_id: str) -> Dict[str, Any]:
    """Retorna detalhes técnicos completos e linha do tempo de transições de um evento especifico."""
    evt = _store.get_event(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail=f"Evento Shadow '{event_id}' não foi encontrado.")

    alert = InternalAlertEngine.format_market_alert(evt)
    transitions = _store.get_transitions(event_id)

    return {
        "alert": alert,
        "raw_event": evt.__dict__,
        "timeline": [t.__dict__ for t in transitions],
        "evidence_payload": evt.evidence,
    }


@router.get("/active")
def list_active_shadow_alerts() -> List[Dict[str, Any]]:
    """Retorna alertas ativos (ARMED, ACTIVATED) para a seção de Alertas de Mercado do Painel."""
    active_evts = _store.list_active_events()
    return [InternalAlertEngine.format_market_alert(e) for e in active_evts]


@router.get("/history")
def list_completed_shadow_history() -> List[Dict[str, Any]]:
    """Retorna o histórico completo de eventos prospectivos finalizados do Shadow Mode."""
    all_evts = _store.list_history_events()
    completed = [e for e in all_evts if e.current_state in ("TARGET_2R", "STOPPED", "EXPIRED", "INVALIDATED")]
    return [InternalAlertEngine.format_market_alert(e) for e in completed]


@router.get("/statistics")
def get_shadow_statistics() -> Dict[str, Any]:
    """Retorna estatísticas prospectivas estritas do Shadow Mode separadas do histórico de pesquisa."""
    stats = _store.get_shadow_statistics(started_at=_scanner.shadow_started_at)
    return {
        "shadow_started_at": stats.shadow_started_at,
        "total_events_detected": stats.total_events_detected,
        "armed_count": stats.armed_count,
        "activated_count": stats.activated_count,
        "targets_reached_count": stats.targets_reached_count,
        "stops_reached_count": stats.stops_reached_count,
        "expired_count": stats.expired_count,
        "invalidated_count": stats.invalidated_count,
        "open_count": stats.open_count,
        "win_rate_shadow": stats.win_rate_shadow,
        "net_r_shadow": stats.net_r_shadow,
        "expectancy_r_shadow": stats.expectancy_r_shadow,
        "profit_factor_shadow": stats.profit_factor_shadow,
        "max_drawdown_r_shadow": stats.max_drawdown_r_shadow,
        "mfe_median_r": stats.mfe_median_r,
        "mae_median_r": stats.mae_median_r,
        "average_holding_bars": stats.average_holding_bars,
        "historical_research_reference": {
            "net_r_research": 49.24,
            "profit_factor_research": 1.25,
            "expectancy_research": 0.12,
            "max_dd_research": 17.15,
            "oos_pf_research": 1.12,
            "sample_type": "HISTORICAL_RESEARCH_DO_NOT_MIX",
        },
    }


@router.get("/heartbeat")
def get_shadow_heartbeat() -> Dict[str, Any]:
    """Retorna o relatório completo de heartbeat, telemetria e estado operacional das 39 combinações (READ-ONLY)."""
    return _store.get_shadow_heartbeat(candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id)


@router.get("/scanners")
def get_scanner_state_list() -> List[Dict[str, Any]]:
    """Retorna o estado de execução e telemetria do scanner prospectivo para as 39 combinações de mercado."""
    hb = _store.get_shadow_heartbeat(candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id)
    return hb.get("scanners", [])


# NOTE: /events/recent foi movido para ANTES de /events/{event_id} (ver acima) para evitar conflito de rotas FastAPI.


@router.get("/navigation/{event_id}")
def get_shadow_event_navigation(event_id: str) -> Dict[str, Any]:
    """Retorna payload de navegação para o frontend abrir o ativo/timeframe/candle correto."""
    evt = _store.get_event(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail=f"Evento '{event_id}' não encontrado.")
    return {
        "event_id": event_id,
        "symbol": evt.symbol,
        "timeframe": evt.timeframe,
        "direction": evt.direction,
        "confluence_time": evt.confluence_time,
        "activation_level": evt.activation_level,
        "initial_stop": evt.initial_stop,
        "target_2R": evt.target_2R,
        "current_state": evt.current_state,
        "evidence": evt.evidence or {},
        "pivot_1_time": evt.pivot_1_time,
        "pivot_1_price": evt.pivot_1_price,
        "pivot_1_rsi": evt.pivot_1_rsi,
        "pivot_2_time": evt.pivot_2_time,
        "pivot_2_price": evt.pivot_2_price,
        "pivot_2_rsi": evt.pivot_2_rsi,
    }


@router.get("/catalog")
def get_shadow_catalog() -> Dict[str, Any]:
    """Retorna o Shadow Universe imutável (13 ativos × 3 timeframes = 39 combinações).
    INDEPENDENTE da watchlist do usuário."""
    from backend.services.shadow_scanner import FOREX_ASSETS, METALS_ASSETS, CRYPTO_ASSETS
    combinations = []
    for sym in SHADOW_ASSETS:
        for tf in SHADOW_TIMEFRAMES:
            if sym in FOREX_ASSETS:
                asset_class = "FOREX"
            elif sym in METALS_ASSETS:
                asset_class = "METALS"
            else:
                asset_class = "CRYPTO"
            combinations.append({
                "symbol": sym,
                "asset_class": asset_class,
                "timeframe": tf,
            })
    return {
        "total_assets": len(SHADOW_ASSETS),
        "total_timeframes": len(SHADOW_TIMEFRAMES),
        "total_combinations": len(combinations),
        "assets": SHADOW_ASSETS,
        "timeframes": SHADOW_TIMEFRAMES,
        "combinations": combinations,
        "note": "Shadow Universe é imutável e independente da watchlist do usuário.",
    }
