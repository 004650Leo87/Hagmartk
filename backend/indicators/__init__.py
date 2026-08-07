from .base import BaseIndicator, IndicatorRegistry
from .moving_averages import EMAIndicator, SMAIndicator
from .rsi import RSIIndicator

# Registra indicadores padrão na fábrica global
IndicatorRegistry.register("rsi", RSIIndicator)
IndicatorRegistry.register("ema", EMAIndicator)
IndicatorRegistry.register("sma", SMAIndicator)

__all__ = [
    "BaseIndicator",
    "IndicatorRegistry",
    "RSIIndicator",
    "EMAIndicator",
    "SMAIndicator",
]
