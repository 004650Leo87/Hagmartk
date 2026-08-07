from __future__ import annotations

from typing import Any, Dict, List, Optional
from backend.strategies.base import BenchmarkSMAStrategy, StrategyRegistry


class StrategyService:
    def __init__(self) -> None:
        # Registra a estratégia de benchmark inicial se ainda não registrada
        if not StrategyRegistry.get("BENCHMARK_SMA"):
            StrategyRegistry.register(BenchmarkSMAStrategy())

    def list_strategies(self) -> List[Dict[str, Any]]:
        return StrategyRegistry.list_all()

    def get_strategy(self, strategy_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        strategy = StrategyRegistry.get(strategy_id, version)
        if not strategy:
            return None
        return {
            "strategy_id": strategy.strategy_id,
            "name": strategy.name,
            "version": strategy.version,
            "description": strategy.description,
            "allowed_timeframes": strategy.allowed_timeframes,
            "warmup_bars": strategy.warmup_bars,
            "allow_open_candle": strategy.allow_open_candle,
            "parameters": strategy.parameters,
        }
