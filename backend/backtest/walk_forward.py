from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd

from backend.backtest.engine import BacktestEngine
from backend.backtest.metrics import BacktestMetrics, calculate_metrics
from backend.backtest.simulator import CostsConfig, IntrabarPolicy
from backend.strategies.base import BaseStrategy


@dataclass
class WalkForwardWindow:
    window_id: int
    start_train: str
    end_train: str
    start_test: str
    end_test: str
    trades_train: int
    trades_test: int
    net_result_train: float
    net_result_test: float
    expectancy_train: float
    expectancy_test: float
    profit_factor_train: float
    profit_factor_test: float
    average_R_train: float
    average_R_test: float
    max_drawdown_train: float
    max_drawdown_test: float


@dataclass
class WalkForwardReport:
    window_type: str = "rolling"  # "rolling" ou "expanding"
    train_ratio: float = 0.70
    test_ratio: float = 0.30
    num_windows: int = 4
    windows: List[WalkForwardWindow] = field(default_factory=list)
    overall_out_of_sample_net: float = 0.0
    overall_out_of_sample_trades: int = 0
    stability_pass: bool = False



def run_walk_forward_analysis(
    df: pd.DataFrame,
    strategy: BaseStrategy,
    symbol: str,
    timeframe: str,
    costs: Optional[CostsConfig] = None,
    intrabar_policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE,
    num_windows: int = 4,
    train_ratio: float = 0.70,
    window_type: str = "rolling",
) -> WalkForwardReport:
    """Executa a análise Walk-Forward sem vazamento temporal (Zero Lookahead Bias).

    Nesta versão de referência, os parâmetros da estratégia permanecem idênticos entre TRAIN e TEST
    para medir a estabilidade temporal da mesma configuração ao longo de diferentes janelas históricas.
    """
    if df is None or len(df) < strategy.warmup_bars + 30:
        return WalkForwardReport(
            window_type=window_type,
            train_ratio=train_ratio,
            test_ratio=1.0 - train_ratio,
            num_windows=0,
        )

    n_bars = len(df)
    window_size = n_bars // num_windows
    report = WalkForwardReport(
        window_type=window_type,
        train_ratio=train_ratio,
        test_ratio=1.0 - train_ratio,
        num_windows=num_windows,
    )

    engine = BacktestEngine(strategy=strategy, intrabar_policy=intrabar_policy, costs=costs)
    test_simulations = []

    for w in range(num_windows):
        if window_type == "expanding":
            train_start_idx = 0
            train_end_idx = int((w + 1) * window_size * train_ratio)
            test_start_idx = train_end_idx
            test_end_idx = min(n_bars, int((w + 1) * window_size))
        else:  # rolling
            w_start = w * window_size
            w_end = min(n_bars, (w + 1) * window_size) if w < num_windows - 1 else n_bars
            w_len = w_end - w_start
            train_start_idx = w_start
            train_end_idx = w_start + int(w_len * train_ratio)
            test_start_idx = train_end_idx
            test_end_idx = w_end

        if train_end_idx - train_start_idx < strategy.warmup_bars + 10 or test_end_idx - test_start_idx < 5:
            continue

        train_df = df.iloc[train_start_idx:train_end_idx].reset_index(drop=True)
        test_df = df.iloc[train_end_idx:test_end_idx].reset_index(drop=True)

        exp_train = engine.run_experiment(train_df, symbol=symbol, timeframe=timeframe)
        exp_test = engine.run_experiment(test_df, symbol=symbol, timeframe=timeframe)

        m_tr = exp_train.metrics
        m_te = exp_test.metrics

        sims_tr = exp_train.simulations
        sims_te = exp_test.simulations
        test_simulations.extend(sims_te)

        avg_r_tr = float(pd.Series([s.r_multiple_net for s in sims_tr]).mean()) if sims_tr else 0.0
        avg_r_te = float(pd.Series([s.r_multiple_net for s in sims_te]).mean()) if sims_te else 0.0

        wf_window = WalkForwardWindow(
            window_id=w + 1,
            start_train=str(train_df["time"].iloc[0]),
            end_train=str(train_df["time"].iloc[-1]),
            start_test=str(test_df["time"].iloc[0]),
            end_test=str(test_df["time"].iloc[-1]),
            trades_train=m_tr.total_trades,
            trades_test=m_te.total_trades,
            net_result_train=m_tr.net_result,
            net_result_test=m_te.net_result,
            expectancy_train=m_tr.expectancy,
            expectancy_test=m_te.expectancy,
            profit_factor_train=m_tr.profit_factor,
            profit_factor_test=m_te.profit_factor,
            average_R_train=avg_r_tr,
            average_R_test=avg_r_te,
            max_drawdown_train=m_tr.max_drawdown,
            max_drawdown_test=m_te.max_drawdown,
        )
        report.windows.append(wf_window)

    report.overall_out_of_sample_trades = len(test_simulations)
    report.overall_out_of_sample_net = float(sum(s.net_profit for s in test_simulations))
    positive_test_windows = sum(1 for w in report.windows if w.net_result_test > 0)
    report.stability_pass = (positive_test_windows >= len(report.windows) / 2.0) if report.windows else False

    return report
