from .base import BaseStrategy, BenchmarkSMAStrategy, StrategyRegistry
from .hdm_divergence import HDMDivergenceStrategy
from .trend_reference import HagmartkTrendReferenceStrategy

__all__ = [
    "BaseStrategy",
    "BenchmarkSMAStrategy",
    "HDMDivergenceStrategy",
    "HagmartkTrendReferenceStrategy",
    "StrategyRegistry",
]

