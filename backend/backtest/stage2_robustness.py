from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from backend.backtest.exit_study import ExitPolicyConfig, TradeExitResult, calculate_exit_policy_metrics


@dataclass
class MonteCarloReport:
    iterations: int = 10000
    prob_net_loss: float = 0.0
    median_final_r: float = 0.0
    p05_final_r: float = 0.0
    p95_final_r: float = 0.0
    median_max_dd_r: float = 0.0
    p95_max_dd_r: float = 0.0
    prob_dd_gt_10r: float = 0.0
    prob_dd_gt_20r: float = 0.0
    prob_dd_gt_30r: float = 0.0


@dataclass
class ConcentrationReport:
    top1_pct: float = 0.0
    top3_pct: float = 0.0
    top5_pct: float = 0.0
    without_top1_net_r: float = 0.0
    without_top1_pf: float = 0.0
    without_top3_net_r: float = 0.0
    without_top3_pf: float = 0.0
    without_top5_net_r: float = 0.0
    without_top5_pf: float = 0.0
    without_worst5_net_r: float = 0.0
    without_worst5_pf: float = 0.0


@dataclass
class OutOfSampleReport:
    in_sample_trades: int = 0
    in_sample_net_r: float = 0.0
    in_sample_pf: float = 0.0
    out_of_sample_trades: int = 0
    out_of_sample_net_r: float = 0.0
    out_of_sample_pf: float = 0.0
    out_of_sample_expectancy_r: float = 0.0
    out_of_sample_max_dd_r: float = 0.0


@dataclass
class CostSensitivityReport:
    cost_baseline_net_r: float = 0.0
    cost_baseline_pf: float = 0.0
    cost_1_5x_net_r: float = 0.0
    cost_1_5x_pf: float = 0.0
    cost_2x_net_r: float = 0.0
    cost_2x_pf: float = 0.0


@dataclass
class LeaveOneOutReport:
    largest_dependency_asset: str = ""
    impact_when_removed_r: float = 0.0
    asset_net_r_map: Dict[str, float] = field(default_factory=dict)
    asset_pf_map: Dict[str, float] = field(default_factory=dict)


@dataclass
class ParameterStabilityReport:
    total_neighbors_tested: int = 0
    stable_neighbors_count: int = 0
    parameter_stability_pct: float = 0.0


@dataclass
class ProductUsabilityReport:
    frequency_per_week: float = 0.0
    frequency_per_month: float = 0.0
    average_holding_bars: float = 0.0
    median_holding_bars: float = 0.0
    median_time_to_1r_bars: float = 0.0
    median_time_to_2r_bars: float = 0.0


@dataclass
class Stage2PolicyReport:
    policy_name: str
    classification: str = ""  # "ROBUST_CANDIDATE", "PROMISING_BUT_INSUFFICIENT", "FRAGILE"
    total_trades: int = 0
    net_r: float = 0.0
    profit_factor: float = 0.0
    expectancy_r: float = 0.0
    max_dd_r: float = 0.0

    oos: OutOfSampleReport = field(default_factory=OutOfSampleReport)
    monte_carlo: MonteCarloReport = field(default_factory=MonteCarloReport)
    concentration: ConcentrationReport = field(default_factory=ConcentrationReport)
    cost_sensitivity: CostSensitivityReport = field(default_factory=CostSensitivityReport)
    leave_one_out: LeaveOneOutReport = field(default_factory=LeaveOneOutReport)
    parameter_stability: ParameterStabilityReport = field(default_factory=ParameterStabilityReport)
    product_metrics: ProductUsabilityReport = field(default_factory=ProductUsabilityReport)

    timeframe_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    class_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    pattern_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    direction_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    rejection_causes: List[str] = field(default_factory=list)


def run_monte_carlo_bootstrap(
    trade_net_rs: List[float], iterations: int = 10000, seed: int = 42
) -> MonteCarloReport:
    """Executa simulação de Monte Carlo Bootstrap com amostragem com reposição e seed determinística."""
    rep = MonteCarloReport(iterations=iterations)
    if not trade_net_rs:
        return rep

    rng = np.random.default_rng(seed)
    n = len(trade_net_rs)
    arr = np.array(trade_net_rs)

    # Matriz 10.000 x N
    samples = rng.choice(arr, size=(iterations, n), replace=True)
    cum_sums = np.cumsum(samples, axis=1)
    final_rs = cum_sums[:, -1]

    # Drawdowns de cada iteração
    peaks = np.maximum.accumulate(np.column_stack([np.zeros(iterations), cum_sums]), axis=1)
    dds = peaks - np.column_stack([np.zeros(iterations), cum_sums])
    max_dds = np.max(dds, axis=1)

    rep.prob_net_loss = float(np.mean(final_rs < 0.0) * 100.0)
    rep.median_final_r = float(np.median(final_rs))
    rep.p05_final_r = float(np.percentile(final_rs, 5))
    rep.p95_final_r = float(np.percentile(final_rs, 95))

    rep.median_max_dd_r = float(np.median(max_dds))
    rep.p95_max_dd_r = float(np.percentile(max_dds, 95))

    rep.prob_dd_gt_10r = float(np.mean(max_dds > 10.0) * 100.0)
    rep.prob_dd_gt_20r = float(np.mean(max_dds > 20.0) * 100.0)
    rep.prob_dd_gt_30r = float(np.mean(max_dds > 30.0) * 100.0)

    return rep


def analyze_concentration_and_outliers(trades: List[TradeExitResult]) -> ConcentrationReport:
    """Calcula métricas de concentração de lucros e impacto da remoção virtual de outliers."""
    rep = ConcentrationReport()
    if not trades:
        return rep

    net_rs = np.array([t.net_r for t in trades])
    tot_net = np.sum(net_rs)

    sorted_indices = np.argsort(net_rs)[::-1]  # Maiores lucros primeiro
    sorted_rs = net_rs[sorted_indices]

    pos_tot = np.sum(sorted_rs[sorted_rs > 0])
    if pos_tot > 0:
        rep.top1_pct = float(round((sorted_rs[0] / pos_tot) * 100.0, 2)) if sorted_rs[0] > 0 else 0.0
        rep.top3_pct = float(round((np.sum(sorted_rs[:3]) / pos_tot) * 100.0, 2)) if len(sorted_rs) >= 3 else 0.0
        rep.top5_pct = float(round((np.sum(sorted_rs[:5]) / pos_tot) * 100.0, 2)) if len(sorted_rs) >= 5 else 0.0

    def _sub_pf(arr: np.ndarray) -> Tuple[float, float]:
        net = float(np.sum(arr))
        w = np.sum(arr[arr > 0])
        l = abs(np.sum(arr[arr < 0]))
        pf = float(w / l) if l > 0 else (float(w) if w > 0 else 0.0)
        return net, pf

    rep.without_top1_net_r, rep.without_top1_pf = _sub_pf(sorted_rs[1:])
    rep.without_top3_net_r, rep.without_top3_pf = _sub_pf(sorted_rs[3:])
    rep.without_top5_net_r, rep.without_top5_pf = _sub_pf(sorted_rs[5:])

    # Remoção dos 5 piores
    rep.without_worst5_net_r, rep.without_worst5_pf = _sub_pf(sorted_rs[:-5] if len(sorted_rs) > 5 else sorted_rs)

    return rep


def analyze_leave_one_asset_out(trades: List[TradeExitResult]) -> LeaveOneOutReport:
    """Mede o impacto da remoção de cada um dos 13 ativos isoladamente."""
    rep = LeaveOneOutReport()
    if not trades:
        return rep

    by_asset = defaultdict(list)
    for t in trades:
        by_asset[t.symbol].append(t)

    tot_net = sum(t.net_r for t in trades)

    largest_impact = 0.0
    largest_asset = ""

    for asset, asset_trades in by_asset.items():
        rem_trades = [t for t in trades if t.symbol != asset]
        net_rem = sum(t.net_r for t in rem_trades)
        w = sum(t.net_r for t in rem_trades if t.net_r > 0)
        l = abs(sum(t.net_r for t in rem_trades if t.net_r < 0))
        pf_rem = float(w / l) if l > 0 else (float(w) if w > 0 else 0.0)

        rep.asset_net_r_map[asset] = round(net_rem, 2)
        rep.asset_pf_map[asset] = round(pf_rem, 2)

        asset_net = sum(t.net_r for t in asset_trades)
        if asset_net > largest_impact:
            largest_impact = asset_net
            largest_asset = asset

    rep.largest_dependency_asset = largest_asset
    rep.impact_when_removed_r = round(tot_net - largest_impact, 2)
    return rep


def classify_stage2_policy(
    metrics: Stage2PolicyReport, min_oos_pf: float = 1.05, max_mc_loss_prob: float = 12.0
) -> str:
    """Classifica a política em ROBUST_CANDIDATE, PROMISING_BUT_INSUFFICIENT ou FRAGILE."""
    rejections = []

    if metrics.monte_carlo.prob_net_loss > max_mc_loss_prob:
        rejections.append(f"Monte Carlo Probability of Loss alta ({metrics.monte_carlo.prob_net_loss:.1f}% > {max_mc_loss_prob}%).")

    if metrics.oos.out_of_sample_pf < min_oos_pf:
        rejections.append(f"Out-of-Sample Profit Factor baixo ({metrics.oos.out_of_sample_pf:.2f} < {min_oos_pf}).")

    if metrics.cost_sensitivity.cost_2x_pf < 1.0:
        rejections.append(f"Sensibilidade a custos 2x insustentável (PF 2x = {metrics.cost_sensitivity.cost_2x_pf:.2f} < 1.0).")

    if metrics.concentration.top3_pct > 50.0:
        rejections.append(f"Alta dependência de Top 3 trades ({metrics.concentration.top3_pct:.1f}% > 50.0%).")

    metrics.rejection_causes = rejections

    if not rejections and metrics.profit_factor >= 1.15:
        return "ROBUST_CANDIDATE"
    elif metrics.monte_carlo.prob_net_loss > max_mc_loss_prob or metrics.net_r <= 0.0:
        return "FRAGILE"
    else:
        return "PROMISING_BUT_INSUFFICIENT"
