from __future__ import annotations

import numpy as np
import pandas as pd

from backend.indicators.base import BaseIndicator


class RSIIndicator(BaseIndicator):
    """Indicador RSI / IFR (Relative Strength Index) utilizando o método de suavização de Wilder."""

    def __init__(self, period: int = 14) -> None:
        if period < 1:
            raise ValueError("O período do RSI deve ser maior ou igual a 1.")
        self.period = period
        self.name = f"rsi_{period}"
        self.params = {"period": period}

    @property
    def warmup_period(self) -> int:
        return self.period + 1

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        if df is None or df.empty or "close" not in df.columns:
            return pd.Series(dtype=float)

        closes = df["close"].values
        n = len(closes)
        rsi_values = np.full(n, np.nan)

        if n <= self.period:
            return pd.Series(rsi_values, index=df.index, name=self.name)

        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Média inicial simples (SMA de N períodos dos ganhos e perdas)
        avg_gain = float(np.mean(gains[: self.period]))
        avg_loss = float(np.mean(losses[: self.period]))

        def _calc_rsi(g: float, l: float) -> float:
            if l == 0.0:
                return 100.0 if g > 0.0 else 50.0
            rs = g / l
            return 100.0 - (100.0 / (1.0 + rs))

        rsi_values[self.period] = _calc_rsi(avg_gain, avg_loss)

        # Suavização de Wilder para os candles posteriores
        for i in range(self.period, len(deltas)):
            avg_gain = (avg_gain * (self.period - 1) + gains[i]) / self.period
            avg_loss = (avg_loss * (self.period - 1) + losses[i]) / self.period
            rsi_values[i + 1] = _calc_rsi(avg_gain, avg_loss)

        return pd.Series(rsi_values, index=df.index, name=self.name)
