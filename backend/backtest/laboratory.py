from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.backtest.concentration import ConcentrationReport, analyze_concentration_and_outliers
from backend.backtest.engine import BacktestEngine
from backend.backtest.metrics import BacktestMetrics
from backend.backtest.monte_carlo import MonteCarloReport, run_monte_carlo_bootstrap
from backend.backtest.parameter_robustness import ParameterRobustnessReport, evaluate_parameter_robustness_grid
from backend.backtest.reconciliation import BacktestReconciliationReport, reconcile_backtest
from backend.backtest.simulator import CostsConfig, IntrabarPolicy, TradeSimulation
from backend.backtest.walk_forward import WalkForwardReport, run_walk_forward_analysis
from backend.domain.events import Direction
from backend.strategies.base import BaseStrategy


@dataclass
class RobustnessComponentAudit:
    performance_status: str  # "POSITIVE", "NEGATIVE"
    out_of_sample_stability: str  # "STABLE", "UNSTABLE"
    parameter_stability: str  # "STABLE", "ISOLATED_PEAK"
    trade_concentration: str  # "LOW", "MODERATE", "HIGH", "EXTREME"
    drawdown_risk: str  # "ACCEPTABLE", "HIGH"
    monte_carlo_risk: str  # "LOW", "HIGH"
    sample_size_classification: str  # "INSUFFICIENT_SAMPLE", "LOW_SAMPLE", "MODERATE_SAMPLE", "LARGE_SAMPLE"


@dataclass
class QuantitativeRobustnessLabReport:
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    status: str = "SUCCESS"  # "SUCCESS", "INVALID_EXPERIMENT", "ERROR"
    failure_reason: str = ""
    reconciliation: BacktestReconciliationReport = field(default_factory=BacktestReconciliationReport)
    metrics_overall: Optional[BacktestMetrics] = None
    long_vs_short: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    new_metrics: Dict[str, Any] = field(default_factory=dict)
    concentration: ConcentrationReport = field(default_factory=ConcentrationReport)
    walk_forward: WalkForwardReport = field(default_factory=WalkForwardReport)
    monte_carlo: MonteCarloReport = field(default_factory=MonteCarloReport)
    parameter_robustness: ParameterRobustnessReport = field(default_factory=ParameterRobustnessReport)
    component_audit: Optional[RobustnessComponentAudit] = None
    final_classification: str = "ROBUSTNESS_NOT_EVALUABLE"  # "ROBUSTNESS_NOT_EVALUABLE", "FRAGILE", "PROMISING_BUT_INSUFFICIENT", "ROBUST_CANDIDATE"
    statistical_limitations: List[str] = field(default_factory=list)
    possible_overfitting_signals: List[str] = field(default_factory=list)


class QuantitativeRobustnessLab:
    """Laboratório de Auditoria de Robustez Quantitativa do Hagmartk Strategy Lab."""

    def __init__(
        self,
        strategy: BaseStrategy,
        symbol: str,
        timeframe: str,
        costs: Optional[CostsConfig] = None,
        intrabar_policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE,
    ) -> None:
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.costs = costs or CostsConfig()
        self.intrabar_policy = intrabar_policy

    def run_full_robustness_audit(
        self,
        df: pd.DataFrame,
        run_parameter_grid: bool = True,
        grid_entry_lookbacks: Optional[List[int]] = None,
        grid_exit_lookbacks: Optional[List[int]] = None,
        grid_atr_periods: Optional[List[int]] = None,
        grid_stop_multipliers: Optional[List[float]] = None,
        monte_carlo_sims: int = 10000,
        monte_carlo_seed: Optional[int] = 42,
    ) -> QuantitativeRobustnessLabReport:
        report = QuantitativeRobustnessLabReport(
            strategy_id=self.strategy.strategy_id,
            strategy_version=self.strategy.version,
            symbol=self.symbol,
            timeframe=self.timeframe,
        )

        # 1. Execução Base da Engine de Backtest
        engine = BacktestEngine(
            strategy=self.strategy,
            intrabar_policy=self.intrabar_policy,
            costs=self.costs,
        )
        exp = engine.run_experiment(df, symbol=self.symbol, timeframe=self.timeframe)

        if exp.status != "SUCCESS":
            report.status = "INVALID_EXPERIMENT"
            report.failure_reason = f"Falha no experimento base: {exp.failure_reason}"
            report.final_classification = "ROBUSTNESS_NOT_EVALUABLE"
            return report

        sims = exp.simulations
        report.metrics_overall = exp.metrics

        # 2. Reconciliação Contábil Obrigatória
        recon = reconcile_backtest(sims)
        report.reconciliation = recon
        if not recon.passed:
            report.status = "INVALID_EXPERIMENT"
            report.failure_reason = f"Reconciliação contábil rejeitada: {recon.trades_with_errors} erros em {recon.trades_checked} trades."
            report.final_classification = "ROBUSTNESS_NOT_EVALUABLE"
            return report

        # 3. Novas Métricas de Estatística e Frequência
        net_Rs = [s.r_multiple_net for s in sims] if sims else []
        holding_bars = [s.duration_bars for s in sims] if sims else []

        date_start = pd.to_datetime(df["time"].iloc[0])
        date_end = pd.to_datetime(df["time"].iloc[-1])
        years_span = max(1.0, (date_end - date_start).days / 365.25)
        trade_freq_yr = len(sims) / years_span if sims else 0.0

        report.new_metrics = {
            "median_R": float(np.median(net_Rs)) if net_Rs else 0.0,
            "average_R": float(np.mean(net_Rs)) if net_Rs else 0.0,
            "R_standard_deviation": float(np.std(net_Rs)) if len(net_Rs) > 1 else 0.0,
            "max_consecutive_losses": exp.metrics.max_consecutive_losses,
            "max_consecutive_wins": exp.metrics.max_consecutive_wins,
            "trade_frequency_per_year": float(trade_freq_yr),
            "average_holding_bars": float(np.mean(holding_bars)) if holding_bars else 0.0,
            "median_holding_bars": float(np.median(holding_bars)) if holding_bars else 0.0,
            "sharpe_status": "NOT_AVAILABLE",
            "sharpe_reason": "insufficient/mismatched temporal methodology (trades de duração variável)",
        }

        # 4. Long vs Short Breakdown
        longs = [s for s in sims if s.event.direction in (Direction.BUY, Direction.BULLISH)]
        shorts = [s for s in sims if s.event.direction in (Direction.SELL, Direction.BEARISH)]

        def _dir_stats(sub: List[TradeSimulation]) -> Dict[str, Any]:
            if not sub:
                return {"trades": 0, "net_result": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "average_R": 0.0}
            net = sum(s.net_profit for s in sub)
            wins = sum(s.net_profit for s in sub if s.net_profit > 0)
            losses = abs(sum(s.net_profit for s in sub if s.net_profit < 0))
            pf = (wins / losses) if losses > 0 else (wins if wins > 0 else 0.0)
            wr = sum(1 for s in sub if s.net_profit > 0) / len(sub)
            avg_r = float(np.mean([s.r_multiple_net for s in sub]))
            return {
                "trades": len(sub),
                "net_result": float(net),
                "profit_factor": float(pf),
                "win_rate": float(wr),
                "expectancy": float(net / len(sub)),
                "average_R": avg_r,
            }

        report.long_vs_short = {"LONG": _dir_stats(longs), "SHORT": _dir_stats(shorts)}

        # 5. Análise de Concentração e Outliers
        report.concentration = analyze_concentration_and_outliers(sims)

        # 6. Análise Walk-Forward
        report.walk_forward = run_walk_forward_analysis(
            df=df,
            strategy=self.strategy,
            symbol=self.symbol,
            timeframe=self.timeframe,
            costs=self.costs,
            intrabar_policy=self.intrabar_policy,
        )

        # 7. Simulação Monte Carlo Bootstrap
        report.monte_carlo = run_monte_carlo_bootstrap(
            trades=sims,
            num_simulations=monte_carlo_sims,
            seed=monte_carlo_seed,
        )

        # 8. Robusteza de Parâmetros
        if run_parameter_grid:
            report.parameter_robustness = evaluate_parameter_robustness_grid(
                df=df,
                symbol=self.symbol,
                timeframe=self.timeframe,
                costs=self.costs,
                intrabar_policy=self.intrabar_policy,
                entry_lookbacks=grid_entry_lookbacks,
                exit_lookbacks=grid_exit_lookbacks,
                atr_periods=grid_atr_periods,
                stop_multipliers=grid_stop_multipliers,
            )

        # 9. Classificação do Tamanho da Amostra (Sample Size Warning)
        n_trades = len(sims)
        if n_trades < 30:
            sample_class = "INSUFFICIENT_SAMPLE"
            report.statistical_limitations.append(f"Amostra insuficiente ({n_trades} trades < 30). Conclusões estatísticas fracas.")
        elif n_trades < 50:
            sample_class = "LOW_SAMPLE"
            report.statistical_limitations.append(f"Amostra pequena ({n_trades} trades). Elevada incerteza de amostragem.")
        elif n_trades < 100:
            sample_class = "MODERATE_SAMPLE"
        else:
            sample_class = "LARGE_SAMPLE"

        # Audit dos componentes
        perf_status = "POSITIVE" if exp.metrics.net_result > 0 else "NEGATIVE"
        oos_status = "STABLE" if report.walk_forward.stability_pass else "UNSTABLE"
        param_status = "STABLE" if report.parameter_robustness.is_stable_region else "ISOLATED_PEAK"
        dd_status = "ACCEPTABLE" if exp.metrics.max_drawdown_pct < 25.0 else "HIGH"
        mc_status = "LOW" if report.monte_carlo.prob_final_loss_pct < 20.0 else "HIGH"

        report.component_audit = RobustnessComponentAudit(
            performance_status=perf_status,
            out_of_sample_stability=oos_status,
            parameter_stability=param_status,
            trade_concentration=report.concentration.concentration_risk,
            drawdown_risk=dd_status,
            monte_carlo_risk=mc_status,
            sample_size_classification=sample_class,
        )

        # Identificação de sinais de Overfitting / Fragilidade
        if report.concentration.concentration_risk in ("HIGH", "EXTREME"):
            report.possible_overfitting_signals.append("Alta concentração de resultados em poucos trades vencedores.")
        if param_status == "ISOLATED_PEAK":
            report.possible_overfitting_signals.append("Sensibilidade excessiva aos parâmetros (apenas região estreita é lucrativa).")
        if oos_status == "UNSTABLE":
            report.possible_overfitting_signals.append("Desempenho Out-of-Sample instável nas janelas históricas.")

        # 10. Classificação Final de Robustez
        if sample_class == "INSUFFICIENT_SAMPLE":
            report.final_classification = "ROBUSTNESS_NOT_EVALUABLE"
        elif perf_status == "NEGATIVE" or report.concentration.concentration_risk == "EXTREME":
            report.final_classification = "FRAGILE"
        elif sample_class == "LOW_SAMPLE" or oos_status == "UNSTABLE" or param_status == "ISOLATED_PEAK":
            report.final_classification = "PROMISING_BUT_INSUFFICIENT"
        elif (
            perf_status == "POSITIVE"
            and oos_status == "STABLE"
            and param_status == "STABLE"
            and report.concentration.concentration_risk in ("LOW", "MODERATE")
        ):
            report.final_classification = "ROBUST_CANDIDATE"
        else:
            report.final_classification = "PROMISING_BUT_INSUFFICIENT"

        return report
