from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.backtest.concentration import analyze_concentration_and_outliers
from backend.backtest.data_cache import OHLCDataCache
from backend.backtest.engine import BacktestEngine
from backend.backtest.laboratory import QuantitativeRobustnessLab, QuantitativeRobustnessLabReport
from backend.backtest.profiling import ExecutionProfiler
from backend.backtest.reconciliation import reconcile_backtest
from backend.backtest.simulator import CostsConfig, IntrabarPolicy, TradeSimulation
from backend.strategies.base import BaseStrategy


@dataclass
class FunnelPromotionCriteria:
    """Critérios configuráveis do funil de triagem para promoção do Stage 1 para o Stage 2."""

    enabled: bool = True
    min_trades: int = 30
    min_profit_factor: float = 1.05
    min_expectancy_R: float = 0.02
    max_cost_impact_pct: float = 80.0
    max_drawdown_pct: float = 80.0
    min_trades_per_month: float = 0.2


@dataclass
class Stage1ScreeningResult:
    combo_key: str
    symbol: str
    category: str
    timeframe: str
    promoted_to_stage2: bool
    promotion_reasons: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    total_trades: int = 0
    trades_per_month: float = 0.0
    trades_per_week: float = 0.0
    win_rate: float = 0.0
    gross_pnl: float = 0.0
    total_costs: float = 0.0
    net_pnl: float = 0.0
    gross_R: float = 0.0
    net_R: float = 0.0
    cost_impact_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy_R: float = 0.0
    median_R: float = 0.0
    max_drawdown_pct: float = 0.0
    long_vs_short: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    top3_concentration_pct: float = 0.0
    dataset_hash: str = ""
    stage1_time_sec: float = 0.0


@dataclass
class FunnelPipelineResult:
    stage1_results: List[Stage1ScreeningResult] = field(default_factory=list)
    promoted_keys: List[str] = field(default_factory=list)
    rejected_keys: List[str] = field(default_factory=list)
    stage2_reports: Dict[str, QuantitativeRobustnessLabReport] = field(default_factory=dict)
    profiling: ExecutionProfiler = field(default_factory=ExecutionProfiler)


def evaluate_stage1_screening(
    sims: List[TradeSimulation],
    symbol: str,
    category: str,
    timeframe: str,
    history_years: float,
    criteria: FunnelPromotionCriteria,
    dataset_hash: str = "",
) -> Stage1ScreeningResult:
    """Executa a triagem rápida determinística do Stage 1 e avalia critérios de promoção."""
    t0 = time.perf_counter()
    combo_key = f"{symbol}_{timeframe}"
    res = Stage1ScreeningResult(
        combo_key=combo_key,
        symbol=symbol,
        category=category,
        timeframe=timeframe,
        promoted_to_stage2=False,
        dataset_hash=dataset_hash,
    )

    if not sims or history_years <= 0:
        res.rejection_reasons.append("Nenhuma operação executada ou histórico inválido.")
        res.stage1_time_sec = time.perf_counter() - t0
        return res

    n_trades = len(sims)
    res.total_trades = n_trades
    res.trades_per_month = float(round((n_trades / history_years) / 12.0, 2))
    res.trades_per_week = float(round((n_trades / history_years) / 52.0, 2))

    wins = [s for s in sims if s.net_profit > 0]
    res.win_rate = float(round(len(wins) / n_trades, 4))

    res.gross_pnl = float(round(sum(s.gross_profit for s in sims), 2))
    res.total_costs = float(
        round(
            sum(
                (s.costs.slippage_points * s.costs.point_value)
                + (s.costs.spread_points * s.costs.point_value)
                for s in sims
            ),
            2,
        )
    )
    res.net_pnl = float(round(sum(s.net_profit for s in sims), 2))

    if res.gross_pnl > 0:
        res.cost_impact_pct = float(round((res.total_costs / res.gross_pnl) * 100.0, 2))
    elif res.total_costs > 0:
        res.cost_impact_pct = 100.0
    else:
        res.cost_impact_pct = 0.0

    sum_w_net = sum(s.net_profit for s in wins)
    sum_l_net = abs(sum(s.net_profit for s in sims if s.net_profit < 0))
    res.profit_factor = float(
        round(sum_w_net / sum_l_net, 4) if sum_l_net > 0 else (round(sum_w_net, 4) if sum_w_net > 0 else 0.0)
    )

    net_Rs = [s.r_multiple_net for s in sims]
    res.expectancy_R = float(round(np.mean(net_Rs), 4)) if net_Rs else 0.0
    res.median_R = float(round(np.median(net_Rs), 4)) if net_Rs else 0.0

    # Drawdown percentual simples no PnL acumulado
    eq = np.cumsum([0.0] + [s.net_profit for s in sims])
    pk = np.maximum.accumulate(eq)
    dd = pk - eq
    max_dd = float(np.max(dd))
    pk_max = float(np.max(pk))
    res.max_drawdown_pct = float(round((max_dd / pk_max * 100.0) if pk_max > 0 else 0.0, 2))

    # Long vs Short
    longs = [s for s in sims if s.event.direction.value in ("BUY", "BULLISH")]
    shorts = [s for s in sims if s.event.direction.value in ("SELL", "BEARISH")]

    def _sub_pf(sub: List[TradeSimulation]) -> float:
        if not sub:
            return 0.0
        w = sum(s.net_profit for s in sub if s.net_profit > 0)
        l = abs(sum(s.net_profit for s in sub if s.net_profit < 0))
        return float(round(w / l, 4) if l > 0 else (round(w, 4) if w > 0 else 0.0))

    res.long_vs_short = {
        "LONG": {"trades": len(longs), "profit_factor": _sub_pf(longs)},
        "SHORT": {"trades": len(shorts), "profit_factor": _sub_pf(shorts)},
    }

    # Concentração preliminar Top 3
    sorted_s = sorted(sims, key=lambda x: x.net_profit, reverse=True)
    if res.net_pnl > 0:
        top_3_sum = sum(s.net_profit for s in sorted_s[:3])
        res.top3_concentration_pct = float(round((top_3_sum / res.net_pnl) * 100.0, 2))

    # Avaliação dos Critérios de Promoção
    if not criteria.enabled:
        res.promoted_to_stage2 = True
        res.promotion_reasons.append("Critérios desativados (Pesquisa Exploratória Completa).")
    else:
        rejections = []
        promotions = []

        if res.total_trades < criteria.min_trades:
            rejections.append(f"Amostra insuficiente ({res.total_trades} trades < {criteria.min_trades}).")
        else:
            promotions.append(f"Amostra aprovada ({res.total_trades} trades >= {criteria.min_trades}).")

        if res.profit_factor < criteria.min_profit_factor:
            rejections.append(f"Profit Factor insuficiente ({res.profit_factor:.3f} < {criteria.min_profit_factor}).")
        else:
            promotions.append(f"Profit Factor aprovado ({res.profit_factor:.3f} >= {criteria.min_profit_factor}).")

        if res.expectancy_R < criteria.min_expectancy_R:
            rejections.append(f"Expectancy em R insuficiente ({res.expectancy_R:.4f} < {criteria.min_expectancy_R}).")

        if res.cost_impact_pct > criteria.max_cost_impact_pct:
            rejections.append(f"Impacto de custos excessivo ({res.cost_impact_pct:.1f}% > {criteria.max_cost_impact_pct}%).")

        if res.max_drawdown_pct > criteria.max_drawdown_pct:
            rejections.append(f"Drawdown excessivo ({res.max_drawdown_pct:.1f}% > {criteria.max_drawdown_pct}%).")

        if res.trades_per_month < criteria.min_trades_per_month:
            rejections.append(f"Frequência mensal baixa ({res.trades_per_month:.2f} < {criteria.min_trades_per_month}).")

        if len(rejections) == 0:
            res.promoted_to_stage2 = True
            res.promotion_reasons = promotions
        else:
            res.promoted_to_stage2 = False
            res.rejection_reasons = rejections

    res.stage1_time_sec = time.perf_counter() - t0
    return res
