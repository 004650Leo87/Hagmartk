from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.strategies.hdf.models import (
    PivotEqualityPolicy,
    ReversalPatternType,
    VolumeSource,
)


@dataclass
class PivotPoint:
    index: int
    time: str
    price: float
    is_high: bool
    confirmed_at_index: int
    confirmed_at_time: str


class PivotDetector:
    """Detector genérico e parametrizável de pivôs de alta (Pivot High) e baixa (Pivot Low).

    Proteção temporal contra Lookahead Bias:
    O pivô no índice `i` NÃO está disponível operativamente no índice `i`.
    Ele fica confirmado apenas no índice `i + pivot_right`.
    """

    def __init__(
        self,
        pivot_left: int = 2,
        pivot_right: int = 2,
        equality_policy: PivotEqualityPolicy = PivotEqualityPolicy.STRICT,
    ) -> None:
        self.pivot_left = pivot_left
        self.pivot_right = pivot_right
        self.equality_policy = equality_policy

    def find_pivots(self, df: pd.DataFrame) -> tuple[List[PivotPoint], List[PivotPoint]]:
        """Retorna (pivot_highs, pivot_lows) identificados na série com confirmação sem lookahead."""
        pivot_highs: List[PivotPoint] = []
        pivot_lows: List[PivotPoint] = []

        if df is None or len(df) < self.pivot_left + self.pivot_right + 1:
            return pivot_highs, pivot_lows

        highs = df["high"].values
        lows = df["low"].values
        times = df["time"].values
        n = len(df)

        for i in range(self.pivot_left, n - self.pivot_right):
            left_highs = highs[i - self.pivot_left : i]
            right_highs = highs[i + 1 : i + self.pivot_right + 1]

            if self.equality_policy == PivotEqualityPolicy.STRICT:
                is_p_high = np.all(highs[i] > left_highs) and np.all(highs[i] > right_highs)
            else:
                is_p_high = np.all(highs[i] >= left_highs) and np.all(highs[i] >= right_highs)

            if is_p_high:
                conf_idx = i + self.pivot_right
                pivot_highs.append(
                    PivotPoint(
                        index=i,
                        time=str(times[i]),
                        price=float(highs[i]),
                        is_high=True,
                        confirmed_at_index=conf_idx,
                        confirmed_at_time=str(times[conf_idx]),
                    )
                )

            left_lows = lows[i - self.pivot_left : i]
            right_lows = lows[i + 1 : i + self.pivot_right + 1]

            if self.equality_policy == PivotEqualityPolicy.STRICT:
                is_p_low = np.all(lows[i] < left_lows) and np.all(lows[i] < right_lows)
            else:
                is_p_low = np.all(lows[i] <= left_lows) and np.all(lows[i] <= right_lows)

            if is_p_low:
                conf_idx = i + self.pivot_right
                pivot_lows.append(
                    PivotPoint(
                        index=i,
                        time=str(times[i]),
                        price=float(lows[i]),
                        is_high=False,
                        confirmed_at_index=conf_idx,
                        confirmed_at_time=str(times[conf_idx]),
                    )
                )

        return pivot_highs, pivot_lows


class DivergenceDetector:
    """Detector de Divergência Regular Nível 1 entre preço e RSI."""

    def __init__(
        self,
        min_bars_between_pivots: int = 5,
        max_bars_between_pivots: int = 50,
    ) -> None:
        self.min_bars_between_pivots = min_bars_between_pivots
        self.max_bars_between_pivots = max_bars_between_pivots

    def check_bearish_divergence(
        self, p1: PivotPoint, p2: PivotPoint, rsi_s: pd.Series
    ) -> tuple[bool, Dict[str, Any]]:
        """Bearish Divergence Nível 1: P2 > P1 e RSI2 < RSI1."""
        bars_diff = p2.index - p1.index
        if not (self.min_bars_between_pivots <= bars_diff <= self.max_bars_between_pivots):
            return False, {}

        rsi1 = float(rsi_s.iloc[p1.index]) if p1.index < len(rsi_s) else np.nan
        rsi2 = float(rsi_s.iloc[p2.index]) if p2.index < len(rsi_s) else np.nan

        if pd.isna(rsi1) or pd.isna(rsi2):
            return False, {}

        is_div = (p2.price > p1.price) and (rsi2 < rsi1)

        rsi_class = "NEUTRAL"
        if rsi1 >= 70.0 or rsi2 >= 70.0:
            rsi_class = "ABOVE_70"

        details = {
            "price_delta": p2.price - p1.price,
            "price_delta_pct": ((p2.price - p1.price) / p1.price) * 100.0 if p1.price > 0 else 0.0,
            "rsi_delta": rsi2 - rsi1,
            "bars_between_pivots": bars_diff,
            "rsi_p1": rsi1,
            "rsi_p2": rsi2,
            "rsi_extreme_class": rsi_class,
        }
        return is_div, details

    def check_bullish_divergence(
        self, p1: PivotPoint, p2: PivotPoint, rsi_s: pd.Series
    ) -> tuple[bool, Dict[str, Any]]:
        """Bullish Divergence Nível 1: P2 < P1 e RSI2 > RSI1."""
        bars_diff = p2.index - p1.index
        if not (self.min_bars_between_pivots <= bars_diff <= self.max_bars_between_pivots):
            return False, {}

        rsi1 = float(rsi_s.iloc[p1.index]) if p1.index < len(rsi_s) else np.nan
        rsi2 = float(rsi_s.iloc[p2.index]) if p2.index < len(rsi_s) else np.nan

        if pd.isna(rsi1) or pd.isna(rsi2):
            return False, {}

        is_div = (p2.price < p1.price) and (rsi2 > rsi1)

        rsi_class = "NEUTRAL"
        if rsi1 <= 30.0 or rsi2 <= 30.0:
            rsi_class = "BELOW_30"

        details = {
            "price_delta": p2.price - p1.price,
            "price_delta_pct": ((p2.price - p1.price) / p1.price) * 100.0 if p1.price > 0 else 0.0,
            "rsi_delta": rsi2 - rsi1,
            "bars_between_pivots": bars_diff,
            "rsi_p1": rsi1,
            "rsi_p2": rsi2,
            "rsi_extreme_class": rsi_class,
        }
        return is_div, details


class VolumeFilter:
    """Filtro e análise de Volume Relativo (VolumeMA20)."""

    def __init__(self, ma_period: int = 20) -> None:
        self.ma_period = ma_period

    def evaluate_volume(
        self, df: pd.DataFrame, curr_idx: int, volume_source: VolumeSource = VolumeSource.TICK_VOLUME
    ) -> tuple[float, float, float, str]:
        """Retorna (vol_curr, vol_ma20, relative_vol, bucket)."""
        vol_col = "tick_volume" if "tick_volume" in df.columns else ("volume" if "volume" in df.columns else None)

        if vol_col is None or curr_idx < self.ma_period:
            return 0.0, 0.0, 0.0, "<1.0"

        volumes = df[vol_col].values
        curr_vol = float(volumes[curr_idx])
        ma20 = float(np.mean(volumes[curr_idx - self.ma_period : curr_idx]))

        if ma20 <= 0.0:
            return curr_vol, 0.0, 0.0, "<1.0"

        rel_vol = curr_vol / ma20

        if rel_vol < 1.0:
            bucket = "<1.0"
        elif 1.0 <= rel_vol < 1.2:
            bucket = "1.0-1.2"
        elif 1.2 <= rel_vol < 1.5:
            bucket = "1.2-1.5"
        elif 1.5 <= rel_vol < 2.0:
            bucket = "1.5-2.0"
        else:
            bucket = ">2.0"

        return curr_vol, ma20, rel_vol, bucket


class ReversalPatternDetector:
    """Detector de padrões de reversão de velas (Engulfing, Hammer, Shooting Star)."""

    @staticmethod
    def detect_at(df: pd.DataFrame, idx: int) -> tuple[ReversalPatternType, Dict[str, Any]]:
        if df is None or idx < 1 or idx >= len(df):
            return ReversalPatternType.NONE, {}

        curr = df.iloc[idx]
        prev = df.iloc[idx - 1]

        c_open, c_close = float(curr["open"]), float(curr["close"])
        c_high, c_low = float(curr["high"]), float(curr["low"])
        p_open, p_close = float(prev["open"]), float(prev["close"])

        c_body = abs(c_close - c_open)
        c_range = c_high - c_low
        if c_range <= 0.0:
            return ReversalPatternType.NONE, {}

        upper_shadow = c_high - max(c_open, c_close)
        lower_shadow = min(c_open, c_close) - c_low

        details = {
            "body": c_body,
            "range": c_range,
            "upper_shadow": upper_shadow,
            "lower_shadow": lower_shadow,
            "high": c_high,
            "low": c_low,
        }

        # 1. Bullish Engulfing
        if p_close < p_open and c_close > c_open and c_open <= p_close and c_close >= p_open:
            return ReversalPatternType.BULLISH_ENGULFING, details

        # 2. Bearish Engulfing
        if p_close > p_open and c_close < c_open and c_open >= p_close and c_close <= p_open:
            return ReversalPatternType.BEARISH_ENGULFING, details

        # 3. Hammer
        if lower_shadow >= 2.0 * c_body and upper_shadow <= 0.2 * c_range:
            return ReversalPatternType.HAMMER, details

        # 4. Shooting Star
        if upper_shadow >= 2.0 * c_body and lower_shadow <= 0.2 * c_range:
            return ReversalPatternType.SHOOTING_STAR, details

        return ReversalPatternType.NONE, details
