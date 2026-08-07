from __future__ import annotations

import numpy as np
import pandas as pd

from backend.indicators.base import BaseIndicator


class EMAIndicator(BaseIndicator):
    """Média Móvel Exponencial (EMA) genérica."""

    def __init__(self, period: int = 20, column: str = "close") -> None:
        if period < 1:
            raise ValueError("O período da EMA deve ser maior ou igual a 1.")
        self.period = period
        self.column = column
        self.name = f"ema_{period}"
        self.params = {"period": period, "column": column}

    @property
    def warmup_period(self) -> int:
        return self.period

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        if df is None or df.empty or self.column not in df.columns:
            return pd.Series(dtype=float)

        series = df[self.column]
        if len(series) < self.period:
            return pd.Series(np.nan, index=df.index, name=self.name)

        ema = series.ewm(span=self.period, adjust=False).mean()
        ema_clean = ema.copy()
        ema_clean.iloc[: self.period - 1] = np.nan
        return pd.Series(ema_clean.values, index=df.index, name=self.name)


class SMAIndicator(BaseIndicator):
    """Média Móvel Simples (SMA) genérica."""

    def __init__(self, period: int = 20, column: str = "close") -> None:
        if period < 1:
            raise ValueError("O período da SMA deve ser maior ou igual a 1.")
        self.period = period
        self.column = column
        self.name = f"sma_{period}"
        self.params = {"period": period, "column": column}

    @property
    def warmup_period(self) -> int:
        return self.period

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        if df is None or df.empty or self.column not in df.columns:
            return pd.Series(dtype=float)

        series = df[self.column]
        sma = series.rolling(window=self.period).mean()
        return pd.Series(sma.values, index=df.index, name=self.name)
