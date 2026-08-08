from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd

from backend.backtest.data_quality import validate_data_quality
from backend.backtest.metrics import calculate_metrics
from backend.backtest.simulator import CostsConfig, IntrabarPolicy, simulate_trade_outcome
from backend.domain.experiment import Experiment
from backend.strategies.base import BaseStrategy, StrategyRegistry


class BacktestEngine:
    """Motor cronológico de backtest bar-by-bar do Hagmartk Strategy Lab.

    REQUISITO FUNDAMENTAL: ZERO LOOKAHEAD BIAS.
    A cada barra T, a estratégia recebe estritamente a fatia de histórico até T.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        intrabar_policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE,
        costs: Optional[CostsConfig] = None,
        in_sample_ratio: float = 0.70,
    ) -> None:
        self.strategy = strategy
        self.intrabar_policy = intrabar_policy
        self.costs = costs or CostsConfig()
        self.in_sample_ratio = in_sample_ratio

    def run_experiment(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        broker: str = "MetaTrader5",
    ) -> Experiment:
        experiment = Experiment(
            strategy_id=self.strategy.strategy_id,
            strategy_version=self.strategy.version,
            strategy_parameters=self.strategy.parameters,
            allowed_timeframes=self.strategy.allowed_timeframes,
            symbol=symbol,
            timeframe=timeframe,
            broker=broker,
            costs_config=self.costs,
            intrabar_policy=self.intrabar_policy,
            in_sample_ratio=self.in_sample_ratio,
        )

        # 1. Validação de timeframe permitido para a estratégia
        if not self.strategy.validate_timeframe(timeframe):
            experiment.status = "REJECTED_TIMEFRAME"
            experiment.failure_reason = (
                f"Timeframe '{timeframe}' não é permitido para a estratégia '{self.strategy.strategy_id}'. "
                f"Timeframes permitidos: {self.strategy.allowed_timeframes}"
            )
            return experiment

        # 2. Validação da qualidade dos dados
        quality_report = validate_data_quality(
            df,
            warmup_bars=self.strategy.warmup_bars,
            min_eval_bars=10,
        )
        experiment.data_quality = quality_report
        experiment.total_candles = len(df) if df is not None else 0

        if not quality_report.is_valid:
            experiment.status = "FAILED_DATA_QUALITY"
            experiment.failure_reason = f"Dados rejeitados pela auditoria de qualidade: {quality_report.reasons}"
            return experiment

        experiment.start_date = str(df["time"].iloc[0])
        experiment.end_date = str(df["time"].iloc[-1])

        # 3. Execução Bar-by-Bar Cronológica (Zero Lookahead Bias)
        warmup = self.strategy.warmup_bars
        n_bars = len(df)
        simulations = []

        max_positions = getattr(self.strategy, "max_concurrent_positions_per_symbol", None)
        active_until_idx = -1

        for t_idx in range(warmup, n_bars - 1):
            # Se a estratégia limita 1 posição por ativo e há uma posição ativa, pula a barra T
            if max_positions == 1 and t_idx < active_until_idx:
                continue

            # Fatia contendo ESTRITAMENTE as barras de 0 até t_idx
            history_t = df.iloc[: t_idx + 1].copy()

            # Chamada da estratégia no momento T
            events = self.strategy.evaluate(
                history=history_t,
                symbol=symbol,
                timeframe=timeframe,
                is_closed_bar=True,  # closed candles only por padrão
            )

            if not events:
                continue

            # Para cada evento detectado em T, simula o desfecho nas barras FUTURAS (T+1 até N)
            future_candles = df.iloc[t_idx + 1 :].copy()

            for evt in events:
                simulation = simulate_trade_outcome(
                    event=evt,
                    future_candles=future_candles,
                    costs=self.costs,
                    policy=self.intrabar_policy,
                    full_df=df,
                    entry_index=t_idx,
                )
                simulations.append(simulation)
                if simulation.duration_bars > 0:
                    active_until_idx = t_idx + simulation.duration_bars


        experiment.simulations = simulations

        # 4. Cálculo das métricas gerais
        experiment.metrics = calculate_metrics(simulations)

        # 5. Separação In-Sample (desenvolvimento) vs Out-Of-Sample (validação)
        split_idx = int(n_bars * self.in_sample_ratio)
        in_sample_cutoff_time = str(df["time"].iloc[split_idx])

        in_sample_trades = [t for t in simulations if t.entry_time <= in_sample_cutoff_time]
        out_sample_trades = [t for t in simulations if t.entry_time > in_sample_cutoff_time]

        experiment.in_sample_metrics = calculate_metrics(in_sample_trades)
        experiment.out_of_sample_metrics = calculate_metrics(out_sample_trades)

        experiment.status = "SUCCESS"
        return experiment

    @classmethod
    def run_multi_asset(
        cls,
        strategy: BaseStrategy,
        data_by_symbol: Dict[str, pd.DataFrame],
        timeframe: str,
        intrabar_policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE,
        costs: Optional[CostsConfig] = None,
        in_sample_ratio: float = 0.70,
    ) -> Dict[str, Experiment]:
        """Executa experimentos em lote para múltiplos símbolos com isolamento de erro por ativo."""
        engine = cls(
            strategy=strategy,
            intrabar_policy=intrabar_policy,
            costs=costs,
            in_sample_ratio=in_sample_ratio,
        )

        results: Dict[str, Experiment] = {}

        for sym, df in data_by_symbol.items():
            try:
                exp = engine.run_experiment(df=df, symbol=sym, timeframe=timeframe)
                results[sym] = exp
            except Exception as error:
                exp_failed = Experiment(
                    strategy_id=strategy.strategy_id,
                    strategy_version=strategy.version,
                    symbol=sym,
                    timeframe=timeframe,
                    status="ERROR",
                    failure_reason=f"Erro não tratado no ativo {sym}: {error}",
                )
                results[sym] = exp_failed

        return results
