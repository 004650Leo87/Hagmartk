from __future__ import annotations

import numpy as np
import pandas as pd

from backend.indicators.atr import ATRIndicator
from backend.indicators.rsi import RSIIndicator


def calculate_vectorized_atr(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Cálculo de ATR de Wilder numericamente equivalente à implementação ATRIndicator de referência."""
    indicator = ATRIndicator(period=period)
    return indicator.calculate(df)


def calculate_vectorized_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Cálculo de RSI de Wilder numericamente equivalente à implementação RSIIndicator de referência."""
    indicator = RSIIndicator(period=period)
    return indicator.calculate(df)


def calculate_vectorized_donchian(
    df: pd.DataFrame, entry_period: int = 55, exit_period: int = 20
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Cálculo vetorizado dos canais de Donchian de entrada e saída.

    Retorna (upper_entry, lower_entry, upper_exit, lower_exit) calculados sobre os candles estritamente
    anteriores (.shift(1)) para prevenir Lookahead Bias.
    """
    if df is None or df.empty or not {"high", "low"}.issubset(df.columns):
        empty_s = pd.Series(dtype=float)
        return empty_s, empty_s, empty_s, empty_s

    highs = df["high"]
    lows = df["low"]

    # Donchian upper/lower dos N candles estritamente anteriores (sem incluir a barra atual)
    upper_entry = highs.shift(1).rolling(window=entry_period).max()
    lower_entry = lows.shift(1).rolling(window=entry_period).min()

    upper_exit = highs.shift(1).rolling(window=exit_period).max()
    lower_exit = lows.shift(1).rolling(window=exit_period).min()

    return upper_entry, lower_entry, upper_exit, lower_exit
