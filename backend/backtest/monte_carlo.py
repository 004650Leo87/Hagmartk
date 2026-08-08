from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np

from backend.backtest.simulator import TradeSimulation


@dataclass
class PercentileDistribution:
    p5: float = 0.0
    p25: float = 0.0
    p50: float = 0.0
    p75: float = 0.0
    p95: float = 0.0


@dataclass
class MonteCarloReport:
    num_simulations: int = 10000
    sample_size: int = 0
    seed_used: Optional[int] = 42
    limitation_notice: str = "Bootstrap simples assume independência estatística entre os trades."
    final_R_distribution: PercentileDistribution = field(default_factory=PercentileDistribution)
    expectancy_R_distribution: PercentileDistribution = field(default_factory=PercentileDistribution)
    max_drawdown_R_distribution: PercentileDistribution = field(default_factory=PercentileDistribution)
    max_consecutive_losses_distribution: PercentileDistribution = field(default_factory=PercentileDistribution)
    max_consecutive_wins_distribution: PercentileDistribution = field(default_factory=PercentileDistribution)
    prob_final_loss_pct: float = 0.0  # Probabilidade de terminar <= 0 R
    prob_drawdown_exceeds_20pct: float = 0.0
    prob_drawdown_exceeds_30pct: float = 0.0


def run_monte_carlo_bootstrap(
    trades: List[TradeSimulation],
    num_simulations: int = 10000,
    seed: Optional[int] = 42,
) -> MonteCarloReport:
    """Executa simulação Monte Carlo por reamostragens Bootstrap (com reposição) dos trades reais."""
    if not trades:
        return MonteCarloReport(num_simulations=num_simulations, sample_size=0, seed_used=seed)

    if seed is not None:
        np.random.seed(seed)

    net_Rs = np.array([t.r_multiple_net for t in trades])
    n = len(net_Rs)

    final_Rs = np.zeros(num_simulations)
    expectancies = np.zeros(num_simulations)
    max_dds_R = np.zeros(num_simulations)
    max_cons_losses_arr = np.zeros(num_simulations, dtype=int)
    max_cons_wins_arr = np.zeros(num_simulations, dtype=int)

    for i in range(num_simulations):
        resample = np.random.choice(net_Rs, size=n, replace=True)
        tot_r = float(np.sum(resample))
        final_Rs[i] = tot_r
        expectancies[i] = float(np.mean(resample))

        # Reconstrução da curva de capital e drawdown em R
        eq = np.cumsum(np.insert(resample, 0, 0.0))
        pk = np.maximum.accumulate(eq)
        dd = pk - eq
        max_dds_R[i] = float(np.max(dd))

        # Maior sequência de perdas e ganhos consecutivas
        curr_l = 0
        max_l = 0
        curr_w = 0
        max_w = 0
        for r in resample:
            if r < 0:
                curr_l += 1
                curr_w = 0
                if curr_l > max_l:
                    max_l = curr_l
            elif r > 0:
                curr_w += 1
                curr_l = 0
                if curr_w > max_w:
                    max_w = curr_w
            else:
                curr_l = 0
                curr_w = 0
        max_cons_losses_arr[i] = max_l
        max_cons_wins_arr[i] = max_w

    def _perc(arr: np.ndarray) -> PercentileDistribution:
        return PercentileDistribution(
            p5=float(np.percentile(arr, 5)),
            p25=float(np.percentile(arr, 25)),
            p50=float(np.percentile(arr, 50)),
            p75=float(np.percentile(arr, 75)),
            p95=float(np.percentile(arr, 95)),
        )

    prob_loss = float(np.mean(final_Rs <= 0.0) * 100.0)

    # Probabilidades configuráveis de drawdown em R (ex: DD > 5R ou DD > 10R)
    prob_dd_20 = float(np.mean(max_dds_R > 5.0) * 100.0)
    prob_dd_30 = float(np.mean(max_dds_R > 10.0) * 100.0)

    return MonteCarloReport(
        num_simulations=num_simulations,
        sample_size=n,
        seed_used=seed,
        final_R_distribution=_perc(final_Rs),
        expectancy_R_distribution=_perc(expectancies),
        max_drawdown_R_distribution=_perc(max_dds_R),
        max_consecutive_losses_distribution=_perc(max_cons_losses_arr),
        max_consecutive_wins_distribution=_perc(max_cons_wins_arr),
        prob_final_loss_pct=prob_loss,
        prob_drawdown_exceeds_20pct=prob_dd_20,
        prob_drawdown_exceeds_30pct=prob_dd_30,
    )
