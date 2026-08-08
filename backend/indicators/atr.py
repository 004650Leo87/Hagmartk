from __future__ import annotations

import numpy as np
import pandas as pd

from backend.indicators.base import BaseIndicator


class ATRIndicator(BaseIndicator):
    """Indicador ATR (Average True Range) utilizando a fórmula de True Range e suavização de Wilder."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError("O período do ATR deve ser maior ou igual a 1.")
        self.period = period
        self.name = f"atr_{period}"
        self.params = {"period": period}

    @property
    def warmup_period(self) -> int:
        # Período mínimo de candles para calcular o primeiro ATR (20 barras + 1 fecho prévio = 21)
        return self.period + 1

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        if df is None or df.empty or not {"high", "low", "close"}.issubset(df.columns):
            return pd.Series(dtype=float)

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        n = len(df)

        atr_values = np.full(n, np.nan)
        if n < self.period + 1:
            return pd.Series(atr_values, index=df.index, name=self.name)

        # Cálculo do True Range (TR)
        tr = np.zeros(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            hl = highs[i] - lows[i]
            hcp = abs(highs[i] - closes[i - 1])
            lcp = abs(lows[i] - closes[i - 1])
            tr[i] = max(hl, hcp, lcp)

        # Média inicial simples dos primeiros `period` TRs (índices 1 a period inclusive)
        initial_atr = float(np.mean(tr[1 : self.period + 1]))
        atr_values[self.period] = initial_atr

        # Suavização de Wilder para os candles subsequentes:
        # ATR_t = (ATR_{t-1} * (period - 1) + TR_t) / period
        curr_atr = initial_atr
        for i in range(self.period + 1, n):
            curr_atr = (curr_atr * (self.period - 1) + tr[i]) / self.period
            atr_values[i] = curr_atr

        return pd.Series(atr_values, index=df.index, name=self.name)
