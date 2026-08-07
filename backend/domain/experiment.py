from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from backend.backtest.data_quality import DataQualityReport
from backend.backtest.metrics import BacktestMetrics
from backend.backtest.simulator import CostsConfig, IntrabarPolicy, TradeSimulation


@dataclass
class Experiment:
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    strategy_version: str = ""
    strategy_parameters: Dict[str, Any] = field(default_factory=dict)
    allowed_timeframes: List[str] = field(default_factory=list)
    symbol: str = ""
    timeframe: str = ""
    broker: str = "MetaTrader5"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_candles: int = 0
    costs_config: CostsConfig = field(default_factory=CostsConfig)
    intrabar_policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE
    in_sample_ratio: float = 0.70
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "PENDING"  # "SUCCESS", "FAILED_DATA_QUALITY", "REJECTED_TIMEFRAME", "ERROR"
    failure_reason: Optional[str] = None
    data_quality: Optional[DataQualityReport] = None
    metrics: Optional[BacktestMetrics] = None
    in_sample_metrics: Optional[BacktestMetrics] = None
    out_of_sample_metrics: Optional[BacktestMetrics] = None
    simulations: List[TradeSimulation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converte o experimento para dicionário serializável em JSON."""
        return {
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "strategy_parameters": self.strategy_parameters,
            "allowed_timeframes": self.allowed_timeframes,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "broker": self.broker,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_candles": self.total_candles,
            "costs_config": {
                "spread_points": self.costs_config.spread_points,
                "point_value": self.costs_config.point_value,
                "commission_per_trade": self.costs_config.commission_per_trade,
                "slippage_points": self.costs_config.slippage_points,
                "swap_per_bar": self.costs_config.swap_per_bar,
            },
            "intrabar_policy": self.intrabar_policy.value,
            "in_sample_ratio": self.in_sample_ratio,
            "created_at": self.created_at,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "data_quality": {
                "is_valid": self.data_quality.is_valid,
                "status": self.data_quality.status,
                "total_candles": self.data_quality.total_candles,
                "reasons": self.data_quality.reasons,
            }
            if self.data_quality
            else None,
            "metrics": self.metrics.__dict__ if self.metrics else None,
            "in_sample_metrics": self.in_sample_metrics.__dict__ if self.in_sample_metrics else None,
            "out_of_sample_metrics": self.out_of_sample_metrics.__dict__ if self.out_of_sample_metrics else None,
            "total_simulations": len(self.simulations),
        }
