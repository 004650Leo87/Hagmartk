from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Any, Dict, List, Optional
import pandas as pd

from backend.backtest.engine import BacktestEngine
from backend.backtest.simulator import CostsConfig, IntrabarPolicy
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy


@dataclass
class ParameterCombinationResult:
    parameters: Dict[str, Any]
    total_trades: int
    net_result: float
    expectancy: float
    profit_factor: float
    average_R: float
    max_drawdown: float
    win_rate: float


@dataclass
class ParameterRobustnessReport:
    grid_size: int = 0
    results: List[ParameterCombinationResult] = field(default_factory=list)
    positive_combinations_pct: float = 0.0
    is_stable_region: bool = False
    notes: List[str] = field(default_factory=list)


def evaluate_parameter_robustness_grid(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    costs: Optional[CostsConfig] = None,
    intrabar_policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE,
    entry_lookbacks: Optional[List[int]] = None,
    exit_lookbacks: Optional[List[int]] = None,
    atr_periods: Optional[List[int]] = None,
    stop_multipliers: Optional[List[float]] = None,
) -> ParameterRobustnessReport:
    """Constrói a superfície de estabilidade de parâmetros em torno da configuração de referência."""
    entries = entry_lookbacks or [45, 50, 55, 60, 65]
    exits = exit_lookbacks or [15, 20, 25]
    atrs = atr_periods or [14, 20, 25]
    stops = stop_multipliers or [1.5, 2.0, 2.5]

    report = ParameterRobustnessReport()
    combos = list(itertools.product(entries, exits, atrs, stops))
    report.grid_size = len(combos)

    results = []
    positive_count = 0

    for e_lk, ex_lk, atr_p, st_m in combos:
        strat = HagmartkTrendReferenceStrategy(
            entry_lookback=e_lk,
            exit_lookback=ex_lk,
            atr_period=atr_p,
            stop_n_multiplier=st_m,
        )
        engine = BacktestEngine(strategy=strat, intrabar_policy=intrabar_policy, costs=costs)
        exp = engine.run_experiment(df, symbol=symbol, timeframe=timeframe)

        if exp.status != "SUCCESS":
            continue

        m = exp.metrics
        sims = exp.simulations
        avg_r = float(pd.Series([s.r_multiple_net for s in sims]).mean()) if sims else 0.0

        if m.net_result > 0:
            positive_count += 1

        res = ParameterCombinationResult(
            parameters={
                "entry_lookback": e_lk,
                "exit_lookback": ex_lk,
                "atr_period": atr_p,
                "stop_n_multiplier": st_m,
            },
            total_trades=m.total_trades,
            net_result=m.net_result,
            expectancy=m.expectancy,
            profit_factor=m.profit_factor,
            average_R=avg_r,
            max_drawdown=m.max_drawdown,
            win_rate=m.win_rate,
        )
        results.append(res)

    report.results = results
    tot = len(results)
    report.positive_combinations_pct = (positive_count / tot * 100.0) if tot > 0 else 0.0
    report.is_stable_region = report.positive_combinations_pct >= 50.0

    report.notes.append(
        f"{report.positive_combinations_pct:.1f}% das combinações de parâmetros vizinhos geraram resultado positivo."
    )
    if not report.is_stable_region:
        report.notes.append("ATENÇÃO: Apenas uma minoria dos parâmetros vizinhos é lucrativa, indicando possível pico isolado/overfitting.")

    return report
