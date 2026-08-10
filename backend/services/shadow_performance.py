"""Shadow Performance Engine V1.

Motor determinístico de validação prospectiva do HDF (Hagmartk Divergence Flow).
Mede e consolida os resultados do Shadow Mode sem alterar a matemática da estratégia.

Populações separadas:
1. Opportunity Population (setups detectados/armados)
2. Activation Population (setups ativados)
3. Terminal Trade Population (trades concluídos em TARGET_2R ou STOPPED)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
import numpy as np

from backend.core.time_utils import parse_utc_timestamp
from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import ShadowEvent, ShadowState
from backend.services.shadow_store import ShadowStoreRepository


@dataclass
class NormalizedShadowTrade:
    event_id: str
    symbol: str
    asset_class: str
    timeframe: str
    direction: str

    activated_at: str
    terminal_at: str

    entry_price: float
    initial_stop: float
    target_price: float
    initial_risk: float

    terminal_state: str
    r_multiple: float

    mae_r: Optional[float] = None
    mfe_r: Optional[float] = None

    bars_duration: int = 0
    clock_duration_seconds: float = 0.0
    same_bar_ambiguous: bool = False


@dataclass
class ShadowPerformanceSnapshot:
    generated_at: str
    shadow_started_at: str
    candidate_id: str
    candidate_version: str
    parameter_hash: str
    sample_status: str  # NO_TERMINAL_TRADES | OBSERVATION

    # Dataset & Populations
    total_raw_events: int = 0
    prospective_opportunities: int = 0
    bootstrap_existing_count: int = 0
    activated_count: int = 0
    active_trades_count: int = 0
    terminal_trades_count: int = 0
    wins_count: int = 0
    losses_count: int = 0
    expired_pre_activation_count: int = 0
    invalidated_pre_activation_count: int = 0

    # Conversão
    activation_rate: Optional[float] = None

    # Performance financeira
    win_rate: Optional[float] = None
    loss_rate: Optional[float] = None
    expectancy_r: Optional[float] = None
    total_r: Optional[float] = None
    average_r: Optional[float] = None
    average_win_r: Optional[float] = None
    average_loss_r: Optional[float] = None
    payoff_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    profit_factor_flag: str = "NORMAL"  # NORMAL | NO_LOSSES_YET | NO_TRADES

    # Risco
    max_drawdown_r: Optional[float] = None
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Excursão (R)
    avg_mae_r: Optional[float] = None
    median_mae_r: Optional[float] = None
    max_mae_r: Optional[float] = None
    avg_mfe_r: Optional[float] = None
    median_mfe_r: Optional[float] = None
    max_mfe_r: Optional[float] = None

    # Duração
    avg_duration_bars: Optional[float] = None
    median_duration_bars: Optional[float] = None
    avg_duration_seconds: Optional[float] = None
    median_duration_seconds: Optional[float] = None

    # Qualidade
    same_bar_ambiguous_count: int = 0
    data_quality_warnings: List[str] = field(default_factory=list)

    # Curva de R
    equity_curve_r: List[Dict[str, Any]] = field(default_factory=list)

    # Breakdowns
    breakdowns: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # Referência Histórica Congelada Lado a Lado (Nunca Agregada)
    historical_reference: Dict[str, Any] = field(default_factory=dict)
    comparison: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProspectiveEligibilityFilter:
    """Filtra eventos garantindo que apenas setups originados APÓS shadow_started_at sejam considerados."""

    @staticmethod
    def is_eligible(evt: ShadowEvent, shadow_started_at: str) -> bool:
        if not shadow_started_at:
            return True

        if evt.current_state == ShadowState.BOOTSTRAP_EXISTING.value:
            return False

        if evt.metadata and evt.metadata.get("bootstrap_detected"):
            return False

        shadow_dt = parse_utc_timestamp(shadow_started_at)
        if shadow_dt is None:
            return True

        event_time_str = evt.confluence_time or evt.divergence_confirmed_at or evt.created_at
        event_dt = parse_utc_timestamp(event_time_str)

        if event_dt is not None and event_dt < shadow_dt:
            return False

        return True


class ShadowPerformanceEngine:
    """Motor de cálculo determinístico para métricas de performance prospectiva do Shadow Mode."""

    def __init__(self, store: Optional[ShadowStoreRepository] = None) -> None:
        self.store = store or ShadowStoreRepository()

    def build_snapshot(self, candidate_id: str = "hdf_dvp_exit_2r") -> ShadowPerformanceSnapshot:
        from backend.core.time_utils import now_utc_str

        now_str = now_utc_str()
        session = self.store.get_shadow_session(candidate_id)
        shadow_started_at = session.get("started_at", "") if session else ""

        all_events = self.store.list_history_events()

        # Filtragem por candidato
        candidate_events = [e for e in all_events if e.candidate_id == candidate_id]

        bootstrap_count = 0
        prospective_events: List[ShadowEvent] = []

        for evt in candidate_events:
            if evt.current_state == ShadowState.BOOTSTRAP_EXISTING.value or (
                evt.metadata and evt.metadata.get("bootstrap_detected")
            ):
                bootstrap_count += 1
            elif ProspectiveEligibilityFilter.is_eligible(evt, shadow_started_at):
                prospective_events.append(evt)

        # Classificação por população
        opportunities = prospective_events
        activations = [
            e for e in prospective_events if e.current_state in (
                ShadowState.ACTIVATED.value,
                ShadowState.TARGET_2R.value,
                ShadowState.STOPPED.value,
            )
        ]
        active_trades = [e for e in prospective_events if e.current_state == ShadowState.ACTIVATED.value]
        terminal_events = [
            e for e in prospective_events if e.current_state in (
                ShadowState.TARGET_2R.value,
                ShadowState.STOPPED.value,
            )
        ]

        expired_pre = [
            e for e in prospective_events if e.current_state == ShadowState.EXPIRED.value
        ]
        invalidated_pre = [
            e for e in prospective_events if e.current_state == ShadowState.INVALIDATED.value
        ]

        # Normalização de trades terminais
        normalized_trades: List[NormalizedShadowTrade] = []
        warnings: List[str] = []
        same_bar_count = 0

        for evt in terminal_events:
            norm, warn, is_same_bar = self._normalize_trade(evt)
            if norm:
                normalized_trades.append(norm)
            if warn:
                warnings.append(warn)
            if is_same_bar:
                same_bar_count += 1

        # Ordenar trades por timestamp terminal
        normalized_trades.sort(key=lambda t: (t.terminal_at or t.activated_at, t.event_id))

        wins = [t for t in normalized_trades if t.r_multiple > 0]
        losses = [t for t in normalized_trades if t.r_multiple <= 0]

        total_terminal = len(normalized_trades)

        # Taxa de Ativação (Activation Rate)
        activation_rate = (len(activations) / len(opportunities)) * 100.0 if opportunities else None

        snapshot = ShadowPerformanceSnapshot(
            generated_at=now_str,
            shadow_started_at=shadow_started_at,
            candidate_id=candidate_id,
            candidate_version=HDF_ROBUST_CANDIDATE_V1.candidate_version,
            parameter_hash=HDF_ROBUST_CANDIDATE_V1.compute_parameter_hash(),
            sample_status="NO_TERMINAL_TRADES" if total_terminal == 0 else "OBSERVATION",
            total_raw_events=len(candidate_events),
            prospective_opportunities=len(opportunities),
            bootstrap_existing_count=bootstrap_count,
            activated_count=len(activations),
            active_trades_count=len(active_trades),
            terminal_trades_count=total_terminal,
            wins_count=len(wins),
            losses_count=len(losses),
            expired_pre_activation_count=len(expired_pre),
            invalidated_pre_activation_count=len(invalidated_pre),
            activation_rate=round(activation_rate, 2) if activation_rate is not None else None,
            same_bar_ambiguous_count=same_bar_count,
            data_quality_warnings=warnings,
        )

        # Referência histórica congelada
        snapshot.historical_reference = {
            "candidate_id": HDF_ROBUST_CANDIDATE_V1.candidate_id,
            "version": HDF_ROBUST_CANDIDATE_V1.candidate_version,
            "research_status": HDF_ROBUST_CANDIDATE_V1.research_status,
            "sample_type": "HISTORICAL_RESEARCH_REFERENCE",
            "trades": 417,
            "total_r": 49.24,
            "win_rate": 37.89,
            "profit_factor": 1.25,
            "payoff": 2.0,
            "monte_carlo_pass_rate": 99.8,
            "note": "Referência congelada no Stage 2 Deep Robustness. Não misturada com o Shadow.",
        }

        if total_terminal == 0:
            snapshot.comparison = {
                "status": "WAITING_PROSPECTIVE_SAMPLE",
                "message": "Nenhum trade prospectivo concluído ainda. Aguardando execuções do Shadow Mode.",
            }
            snapshot.breakdowns = self._build_empty_breakdowns()
            return snapshot

        # Métricas financeiras em R
        r_list = [t.r_multiple for t in normalized_trades]
        win_r_list = [t.r_multiple for t in wins]
        loss_r_list = [t.r_multiple for t in losses]

        win_rate = (len(wins) / total_terminal) * 100.0
        loss_rate = (len(losses) / total_terminal) * 100.0
        total_r = sum(r_list)
        expectancy_r = total_r / total_terminal
        average_r = expectancy_r

        avg_win_r = (sum(win_r_list) / len(wins)) if wins else 0.0
        avg_loss_r = (sum(loss_r_list) / len(losses)) if losses else 0.0

        payoff_ratio = (avg_win_r / abs(avg_loss_r)) if (losses and avg_loss_r != 0) else None

        gross_profit = sum(win_r_list)
        gross_loss = abs(sum(loss_r_list))

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
            pf_flag = "NORMAL"
        elif gross_profit > 0:
            profit_factor = None
            pf_flag = "NO_LOSSES_YET"
        else:
            profit_factor = None
            pf_flag = "NO_TRADES"

        # Curva de R Acumulado e Max Drawdown
        equity_curve: List[Dict[str, Any]] = []
        cum_r = 0.0
        peak = 0.0
        max_dd = 0.0

        for t in normalized_trades:
            cum_r += t.r_multiple
            if cum_r > peak:
                peak = cum_r
            dd = peak - cum_r
            if dd > max_dd:
                max_dd = dd

            equity_curve.append({
                "event_id": t.event_id,
                "terminal_at": t.terminal_at,
                "symbol": t.symbol,
                "timeframe": t.timeframe,
                "direction": t.direction,
                "r": round(t.r_multiple, 2),
                "cumulative_r": round(cum_r, 2),
            })

        # Streaks
        max_c_wins = 0
        max_c_losses = 0
        curr_wins = 0
        curr_losses = 0

        for t in normalized_trades:
            if t.r_multiple > 0:
                curr_wins += 1
                curr_losses = 0
                if curr_wins > max_c_wins:
                    max_c_wins = curr_wins
            else:
                curr_losses += 1
                curr_wins = 0
                if curr_losses > max_c_losses:
                    max_c_losses = curr_losses

        # MAE / MFE
        mae_values = [t.mae_r for t in normalized_trades if t.mae_r is not None]
        mfe_values = [t.mfe_r for t in normalized_trades if t.mfe_r is not None]

        # Duração
        bars_values = [t.bars_duration for t in normalized_trades if t.bars_duration > 0]
        secs_values = [t.clock_duration_seconds for t in normalized_trades if t.clock_duration_seconds > 0]

        snapshot.win_rate = round(win_rate, 2)
        snapshot.loss_rate = round(loss_rate, 2)
        snapshot.total_r = round(total_r, 2)
        snapshot.expectancy_r = round(expectancy_r, 2)
        snapshot.average_r = round(average_r, 2)
        snapshot.average_win_r = round(avg_win_r, 2) if wins else None
        snapshot.average_loss_r = round(avg_loss_r, 2) if losses else None
        snapshot.payoff_ratio = round(payoff_ratio, 2) if payoff_ratio is not None else None
        snapshot.profit_factor = round(profit_factor, 2) if profit_factor is not None else None
        snapshot.profit_factor_flag = pf_flag

        snapshot.max_drawdown_r = round(max_dd, 2)
        snapshot.max_consecutive_wins = max_c_wins
        snapshot.max_consecutive_losses = max_c_losses

        snapshot.avg_mae_r = round(float(np.mean(mae_values)), 2) if mae_values else None
        snapshot.median_mae_r = round(float(np.median(mae_values)), 2) if mae_values else None
        snapshot.max_mae_r = round(float(np.max(mae_values)), 2) if mae_values else None

        snapshot.avg_mfe_r = round(float(np.mean(mfe_values)), 2) if mfe_values else None
        snapshot.median_mfe_r = round(float(np.median(mfe_values)), 2) if mfe_values else None
        snapshot.max_mfe_r = round(float(np.max(mfe_values)), 2) if mfe_values else None

        snapshot.avg_duration_bars = round(float(np.mean(bars_values)), 1) if bars_values else None
        snapshot.median_duration_bars = round(float(np.median(bars_values)), 1) if bars_values else None
        snapshot.avg_duration_seconds = round(float(np.mean(secs_values)), 0) if secs_values else None
        snapshot.median_duration_seconds = round(float(np.median(secs_values)), 0) if secs_values else None

        snapshot.equity_curve_r = equity_curve

        # Breakdowns
        snapshot.breakdowns = self._build_breakdowns(opportunities, activations, normalized_trades)

        # Comparação descritiva segura
        snapshot.comparison = {
            "historical_win_rate": 37.89,
            "prospective_win_rate": round(win_rate, 2),
            "win_rate_delta": round(win_rate - 37.89, 2),

            "historical_expectancy_r": 0.118,
            "prospective_expectancy_r": round(expectancy_r, 2),

            "historical_profit_factor": 1.25,
            "prospective_profit_factor": round(profit_factor, 2) if profit_factor is not None else "NO_LOSSES",

            "sample_size_terminal_trades": total_terminal,
            "note": "Comparação puramente descritiva. Amostras reduzidas não constituem validação ou falha definitiva.",
        }

        return snapshot

    def _normalize_trade(self, evt: ShadowEvent) -> tuple[Optional[NormalizedShadowTrade], Optional[str], bool]:
        state = evt.current_state
        if state not in (ShadowState.TARGET_2R.value, ShadowState.STOPPED.value):
            return None, None, False

        r_mult = 2.0 if state == ShadowState.TARGET_2R.value else -1.0
        warning = None
        is_same_bar = evt.metadata.get("same_bar_ambiguous", False) if evt.metadata else False

        terminal_at = evt.updated_at or evt.market_candle_time or evt.activated_at

        bars_dur = evt.bars_since_activation or 0
        clock_dur = 0.0

        if evt.activated_at and terminal_at:
            dt_act = parse_utc_timestamp(evt.activated_at)
            dt_term = parse_utc_timestamp(terminal_at)
            if dt_act and dt_term and dt_term >= dt_act:
                clock_dur = (dt_term - dt_act).total_seconds()

        trade = NormalizedShadowTrade(
            event_id=evt.event_id,
            symbol=evt.symbol,
            asset_class=evt.asset_class or "UNKNOWN",
            timeframe=evt.timeframe,
            direction=evt.direction,
            activated_at=evt.activated_at,
            terminal_at=terminal_at,
            entry_price=evt.entry_price,
            initial_stop=evt.initial_stop,
            target_price=evt.target_2R,
            initial_risk=evt.initial_risk,
            terminal_state=state,
            r_multiple=r_mult,
            mae_r=evt.mae_r_live if evt.mae_r_live != 0.0 else None,
            mfe_r=evt.mfe_r_live if evt.mfe_r_live != 0.0 else None,
            bars_duration=bars_dur,
            clock_duration_seconds=clock_dur,
            same_bar_ambiguous=is_same_bar,
        )

        return trade, warning, is_same_bar

    def _build_empty_breakdowns(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "symbol": [],
            "timeframe": [],
            "direction": [],
            "asset_class": [],
        }

    def _build_breakdowns(
        self,
        opportunities: List[ShadowEvent],
        activations: List[ShadowEvent],
        terminal_trades: List[NormalizedShadowTrade],
    ) -> Dict[str, List[Dict[str, Any]]]:

        def calc_group(group_key_func) -> List[Dict[str, Any]]:
            groups: Dict[str, Dict[str, Any]] = {}

            # 1. Contar Oportunidades por Grupo
            for opp in opportunities:
                key = group_key_func(opp)
                if key not in groups:
                    groups[key] = {
                        "key": key,
                        "opportunities": 0,
                        "activations": 0,
                        "terminal_trades": 0,
                        "wins": 0,
                        "losses": 0,
                        "total_r": 0.0,
                    }
                groups[key]["opportunities"] += 1

            # 2. Contar Ativações por Grupo
            for act in activations:
                key = group_key_func(act)
                if key in groups:
                    groups[key]["activations"] += 1

            # 3. Métricas de Trades por Grupo
            for t in terminal_trades:
                key = t.symbol if group_key_func.__name__ == '<lambda_sym>' else (
                    t.timeframe if group_key_func.__name__ == '<lambda_tf>' else (
                        t.direction if group_key_func.__name__ == '<lambda_dir>' else t.asset_class
                    )
                )
                if key in groups:
                    g = groups[key]
                    g["terminal_trades"] += 1
                    if t.r_multiple > 0:
                        g["wins"] += 1
                    else:
                        g["losses"] += 1
                    g["total_r"] += t.r_multiple

            # 4. Formatar resultados
            result = []
            for k, g in groups.items():
                tt = g["terminal_trades"]
                wr = (g["wins"] / tt * 100.0) if tt > 0 else None
                exp = (g["total_r"] / tt) if tt > 0 else None

                result.append({
                    "key": k,
                    "opportunities": g["opportunities"],
                    "activations": g["activations"],
                    "terminal_trades": tt,
                    "wins": g["wins"],
                    "losses": g["losses"],
                    "total_r": round(g["total_r"], 2),
                    "win_rate": round(wr, 2) if wr is not None else None,
                    "expectancy_r": round(exp, 2) if exp is not None else None,
                })

            result.sort(key=lambda x: x["opportunities"], reverse=True)
            return result

        l_sym = lambda e: e.symbol
        l_sym.__name__ = '<lambda_sym>'

        l_tf = lambda e: e.timeframe
        l_tf.__name__ = '<lambda_tf>'

        l_dir = lambda e: e.direction
        l_dir.__name__ = '<lambda_dir>'

        l_ac = lambda e: e.asset_class or "UNKNOWN"
        l_ac.__name__ = '<lambda_ac>'

        return {
            "symbol": calc_group(l_sym),
            "timeframe": calc_group(l_tf),
            "direction": calc_group(l_dir),
            "asset_class": calc_group(l_ac),
        }
