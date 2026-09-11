from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence, Tuple


DDIX_TRIX_PERIOD = 9
DDIX_TRIX_SIGNAL_PERIOD = 4
DDIX_TRIX_SIGNAL_MODE_CANDIDATES = ("EMA", "SMA")


@dataclass(frozen=True)
class TrixSeries:
    trix: Tuple[float | None, ...]
    signal: Tuple[float | None, ...]
    trix_period: int
    signal_period: int
    signal_mode: str
    provenance: str


@dataclass(frozen=True)
class TrixCrossEvidence:
    cross: str
    bullish: bool
    bearish: bool
    previous_trix: float
    previous_signal: float
    current_trix: float
    current_signal: float
    provenance: str


def _finite(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("DDIX_TRIX_VALUE_NOT_FINITE")
    return number


def ema_series(values: Sequence[float], period: int) -> Tuple[float, ...]:
    if period <= 0:
        raise ValueError("DDIX_TRIX_PERIOD_MUST_BE_POSITIVE")
    if not values:
        raise ValueError("DDIX_TRIX_EMPTY_SERIES")
    clean = tuple(_finite(value) for value in values)
    alpha = 2.0 / (float(period) + 1.0)
    out = [clean[0]]
    for value in clean[1:]:
        out.append((value * alpha) + (out[-1] * (1.0 - alpha)))
    return tuple(out)


def compute_trix_values(
    closes: Sequence[float], period: int = DDIX_TRIX_PERIOD
) -> Tuple[float | None, ...]:
    if len(closes) < 2:
        raise ValueError("DDIX_TRIX_INSUFFICIENT_HISTORY")
    ema1 = ema_series(closes, period)
    ema2 = ema_series(ema1, period)
    ema3 = ema_series(ema2, period)
    values: list[float | None] = [None]
    for previous, current in zip(ema3, ema3[1:]):
        if previous == 0.0:
            values.append(None)
        else:
            values.append(((current - previous) / previous) * 100.0)
    return tuple(values)


def _signal_sma(values: Sequence[float | None], period: int) -> Tuple[float | None, ...]:
    out: list[float | None] = []
    history: list[float] = []
    for value in values:
        if value is None:
            out.append(None)
            continue
        history.append(value)
        if len(history) < period:
            out.append(None)
        else:
            window = history[-period:]
            out.append(sum(window) / float(period))
    return tuple(out)


def _signal_ema(values: Sequence[float | None], period: int) -> Tuple[float | None, ...]:
    if period <= 0:
        raise ValueError("DDIX_TRIX_SIGNAL_PERIOD_MUST_BE_POSITIVE")
    alpha = 2.0 / (float(period) + 1.0)
    out: list[float | None] = []
    previous: float | None = None
    for value in values:
        if value is None:
            out.append(None)
            continue
        previous = value if previous is None else (value * alpha) + (previous * (1.0 - alpha))
        out.append(previous)
    return tuple(out)


def compute_trix_with_signal(
    closes: Sequence[float],
    signal_mode: str,
    trix_period: int = DDIX_TRIX_PERIOD,
    signal_period: int = DDIX_TRIX_SIGNAL_PERIOD,
) -> TrixSeries:
    if signal_period <= 0:
        raise ValueError("DDIX_TRIX_SIGNAL_PERIOD_MUST_BE_POSITIVE")
    mode = str(signal_mode).upper().strip()
    if mode not in DDIX_TRIX_SIGNAL_MODE_CANDIDATES:
        raise ValueError("DDIX_TRIX_SIGNAL_MODE_NOT_APPROVED")
    trix = compute_trix_values(closes, trix_period)
    signal = _signal_ema(trix, signal_period) if mode == "EMA" else _signal_sma(trix, signal_period)
    return TrixSeries(
        trix=trix,
        signal=signal,
        trix_period=trix_period,
        signal_period=signal_period,
        signal_mode=mode,
        provenance="NELOGICA_METAQUOTES_TRIX_FORMULA_DIDI_9_4_SIGNAL_MODE_OPEN",
    )


def classify_trix_cross(
    previous_trix: float,
    previous_signal: float,
    current_trix: float,
    current_signal: float,
) -> TrixCrossEvidence:
    pt = _finite(previous_trix)
    ps = _finite(previous_signal)
    ct = _finite(current_trix)
    cs = _finite(current_signal)
    bullish = pt <= ps and ct > cs
    bearish = pt >= ps and ct < cs
    cross = "BUY_CROSS" if bullish else "SELL_CROSS" if bearish else "NO_CROSS"
    return TrixCrossEvidence(
        cross=cross,
        bullish=bullish,
        bearish=bearish,
        previous_trix=pt,
        previous_signal=ps,
        current_trix=ct,
        current_signal=cs,
        provenance="DIDI_TRIX_LINE_SIGNAL_CROSS_SEMANTIC",
    )
