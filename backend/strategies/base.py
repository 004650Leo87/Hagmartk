from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import pandas as pd

from backend.domain.events import Direction, StrategyEvent


class BaseStrategy(ABC):
    """Classe base abstrata para qualquer estratégia quantitativa do Hagmartk Strategy Lab.

    Não contém nenhuma lógica de estratégia específica.
    Toda futura estratégia (ex: HDM 1.0, HDM 1.1) deverá herdar desta classe.
    """

    strategy_id: str
    name: str
    version: str
    description: str
    allowed_timeframes: List[str]
    parameters: Dict[str, Any]
    warmup_bars: int = 20
    allow_open_candle: bool = False

    def validate_timeframe(self, timeframe: str) -> bool:
        """Verifica se o timeframe é permitido para esta estratégia."""
        if not self.allowed_timeframes:
            return True
        return timeframe in self.allowed_timeframes

    @abstractmethod
    def evaluate(
        self,
        history: pd.DataFrame,
        symbol: str,
        timeframe: str,
        is_closed_bar: bool = True,
    ) -> List[StrategyEvent]:
        """Avalia a estratégia sobre o histórico disponível no instante T.

        REQUISITO FUNDAMENTAL: ZERO LOOKAHEAD BIAS.
        O dataframe `history` contém estritamente barras até a barra T.
        """
        pass


class StrategyRegistry:
    """Registro global de estratégias disponíveis no Strategy Lab."""

    _strategies: Dict[str, BaseStrategy] = {}

    @classmethod
    def register(cls, strategy: BaseStrategy) -> None:
        key = f"{strategy.strategy_id}:{strategy.version}"
        cls._strategies[key] = strategy
        cls._strategies[strategy.strategy_id] = strategy

    @classmethod
    def get(cls, strategy_id: str, version: Optional[str] = None) -> Optional[BaseStrategy]:
        if version:
            return cls._strategies.get(f"{strategy_id}:{version}")
        return cls._strategies.get(strategy_id)

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        seen = set()
        out = []
        for s in cls._strategies.values():
            key = (s.strategy_id, s.version)
            if key not in seen:
                seen.add(key)
                out.append(
                    {
                        "strategy_id": s.strategy_id,
                        "name": s.name,
                        "version": s.version,
                        "description": s.description,
                        "allowed_timeframes": s.allowed_timeframes,
                        "warmup_bars": s.warmup_bars,
                        "allow_open_candle": s.allow_open_candle,
                        "parameters": s.parameters,
                    }
                )
        return out

    @classmethod
    def clear(cls) -> None:
        cls._strategies.clear()


class BenchmarkSMAStrategy(BaseStrategy):
    """Estratégia de benchmark interna utilizada exclusivamente para testes e validação da engine.

    NÃO é uma estratégia de produção nem substitui a HDM.
    """

    def __init__(
        self,
        fast_period: int = 5,
        slow_period: int = 20,
        allowed_timeframes: Optional[List[str]] = None,
    ) -> None:
        self.strategy_id = "BENCHMARK_SMA"
        self.name = "Benchmark SMA Crossover"
        self.version = "1.0"
        self.description = "Estratégia neutra de teste para validação da engine do Strategy Lab"
        self.allowed_timeframes = allowed_timeframes or ["M15", "M30", "H1", "H2", "H4", "D1"]
        self.parameters = {"fast_period": fast_period, "slow_period": slow_period}
        self.warmup_bars = max(fast_period, slow_period) + 2
        self.allow_open_candle = False

    def evaluate(
        self,
        history: pd.DataFrame,
        symbol: str,
        timeframe: str,
        is_closed_bar: bool = True,
    ) -> List[StrategyEvent]:
        if not is_closed_bar and not self.allow_open_candle:
            return []

        fast_p = self.parameters["fast_period"]
        slow_p = self.parameters["slow_period"]

        if len(history) < max(fast_p, slow_p) + 1:
            return []

        # Calcula SMA apenas com dados até a barra T
        closes = history["close"]
        sma_fast = closes.rolling(window=fast_p).mean()
        sma_slow = closes.rolling(window=slow_p).mean()

        curr_fast = sma_fast.iloc[-1]
        curr_slow = sma_slow.iloc[-1]
        prev_fast = sma_fast.iloc[-2]
        prev_slow = sma_slow.iloc[-2]

        if pd.isna(curr_fast) or pd.isna(curr_slow) or pd.isna(prev_fast) or pd.isna(prev_slow):
            return []

        curr_close = closes.iloc[-1]
        timestamp = str(history["time"].iloc[-1])

        # Cruzamento de compra (Fast cruza acima de Slow)
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            stop_loss = curr_close * 0.99
            t1 = curr_close * 1.015
            t2 = curr_close * 1.03
            return [
                StrategyEvent(
                    strategy_id=self.strategy_id,
                    strategy_version=self.version,
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=Direction.BUY,
                    detected_at=timestamp,
                    reference_price=float(curr_close),
                    entry_zone=[float(curr_close * 0.999), float(curr_close * 1.001)],
                    invalidation=float(stop_loss),
                    targets=[float(t1), float(t2)],
                    confidence=0.8,
                    reasons=["SMA Fast crossed above SMA Slow"],
                )
            ]

        # Cruzamento de venda (Fast cruza abaixo de Slow)
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            stop_loss = curr_close * 1.01
            t1 = curr_close * 0.985
            t2 = curr_close * 0.97
            return [
                StrategyEvent(
                    strategy_id=self.strategy_id,
                    strategy_version=self.version,
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=Direction.SELL,
                    detected_at=timestamp,
                    reference_price=float(curr_close),
                    entry_zone=[float(curr_close * 0.999), float(curr_close * 1.001)],
                    invalidation=float(stop_loss),
                    targets=[float(t1), float(t2)],
                    confidence=0.8,
                    reasons=["SMA Fast crossed below SMA Slow"],
                )
            ]

        return []
