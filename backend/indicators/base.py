from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import pandas as pd


class BaseIndicator(ABC):
    """Interface abstrata base para todos os indicadores técnicos do Hagmartk."""

    name: str
    params: Dict[str, Any]

    @property
    @abstractmethod
    def warmup_period(self) -> int:
        """Retorna o número mínimo de candles de warmup necessários para o indicador estabilizar."""
        pass

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """Calcula o indicador sobre o DataFrame de candles.

        REQUISITO FUNDAMENTAL: ZERO LOOKAHEAD BIAS.
        O valor no índice T depende estritamente dos preços até T.
        """
        pass


class IndicatorRegistry:
    """Registro global de fábrica para intanciação dinâmica de indicadores."""

    _indicators: Dict[str, type[BaseIndicator]] = {}

    @classmethod
    def register(cls, key: str, indicator_cls: type[BaseIndicator]) -> None:
        cls._indicators[key.lower()] = indicator_cls

    @classmethod
    def get(cls, key: str, **kwargs: Any) -> Optional[BaseIndicator]:
        indicator_cls = cls._indicators.get(key.lower())
        if not indicator_cls:
            return None
        return indicator_cls(**kwargs)
