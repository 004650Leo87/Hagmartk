from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.backtest.engine import BacktestEngine
from backend.backtest.simulator import CostsConfig, IntrabarPolicy
from backend.core.constants import SUPPORTED_TIMEFRAMES
from backend.domain.experiment import Experiment
from backend.services.market_service import MarketService
from backend.services.strategy_service import StrategyService
from backend.strategies.base import StrategyRegistry


class ExperimentStore:
    """Repositório em memória para persistência dos experimentos de backtest."""

    _experiments: Dict[str, Experiment] = {}

    @classmethod
    def save(cls, experiment: Experiment) -> None:
        cls._experiments[experiment.experiment_id] = experiment

    @classmethod
    def get(cls, experiment_id: str) -> Optional[Experiment]:
        return cls._experiments.get(experiment_id)

    @classmethod
    def list_all(cls) -> List[Experiment]:
        return list(cls._experiments.values())

    @classmethod
    def clear(cls) -> None:
        cls._experiments.clear()


class BacktestService:
    def __init__(self) -> None:
        self.market_service = MarketService()
        self.strategy_service = StrategyService()

    def run_backtest(
        self,
        strategy_id: str,
        symbol: str,
        timeframe: str,
        bars: int = 500,
        offset: int = 0,
        intrabar_policy: str = "CONSERVATIVE",
        spread_points: float = 0.0,
        commission_per_trade: float = 0.0,
        slippage_points: float = 0.0,
        in_sample_ratio: float = 0.70,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executa um backtest para a estratégia solicitada sobre os dados reais do MT5."""
        strategy = StrategyRegistry.get(strategy_id, version)

        if not strategy:
            raise ValueError(f"Estratégia '{strategy_id}' não encontrada no repositório.")

        # Obtém o código numérico do timeframe
        tf_upper = timeframe.upper().strip()
        tf_code = SUPPORTED_TIMEFRAMES.get(tf_upper)

        if tf_code is None:
            raise ValueError(f"Timeframe '{timeframe}' não é suportado pelo MetaTrader 5.")

        # Requisita os candles históricos através do MarketService
        df = self.market_service.candles(
            symbol=symbol,
            timeframe=tf_code,
            bars=bars,
            offset=offset,
        )

        policy_enum = IntrabarPolicy(intrabar_policy.upper())
        costs = CostsConfig(
            spread_points=spread_points,
            commission_per_trade=commission_per_trade,
            slippage_points=slippage_points,
        )

        engine = BacktestEngine(
            strategy=strategy,
            intrabar_policy=policy_enum,
            costs=costs,
            in_sample_ratio=in_sample_ratio,
        )

        experiment = engine.run_experiment(
            df=df,
            symbol=symbol,
            timeframe=tf_upper,
        )

        ExperimentStore.save(experiment)

        return experiment.to_dict()

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        exp = ExperimentStore.get(experiment_id)
        if not exp:
            return None
        return exp.to_dict()

    def list_experiments(self) -> List[Dict[str, Any]]:
        return [exp.to_dict() for exp in ExperimentStore.list_all()]
