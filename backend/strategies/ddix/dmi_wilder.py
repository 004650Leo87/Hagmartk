from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence


@dataclass(frozen=True)
class OhlcBar:
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class WilderDmiPoint:
    index: int
    tr: float | None
    plus_dm: float | None
    minus_dm: float | None
    atr_smma: float | None
    plus_dm_smma: float | None
    minus_dm_smma: float | None
    di_plus: float | None
    di_minus: float | None
    dx: float | None
    adx: float | None


PROVENANCE = "METAQUOTES_PUBLISHED_IADXWILDER_FORMULA"

def _finite(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("DDIX_WILDER_VALUE_NOT_FINITE")
    return number


def _validate_bar(bar: OhlcBar) -> OhlcBar:
    high = _finite(bar.high)
    low = _finite(bar.low)
    close = _finite(bar.close)
    if high < low:
        raise ValueError("DDIX_WILDER_HIGH_BELOW_LOW")
    return OhlcBar(high=high, low=low, close=close)


def _raw_movement(previous: OhlcBar, current: OhlcBar) -> tuple[float, float, float]:
    up = current.high - previous.high
    down = previous.low - current.low
    plus_dm = up if up > 0.0 else 0.0
    minus_dm = down if down > 0.0 else 0.0
    tr = max(
        abs(current.high - current.low),
        abs(current.high - previous.close),
        abs(current.low - previous.close),
    )
    return tr, plus_dm, minus_dm

def _smma_step(previous: float, current: float, period: int) -> float:
    return ((previous * float(period - 1)) + current) / float(period)


def _ratios(
    atr: float,
    plus_smma: float,
    minus_smma: float,
) -> tuple[float, float, float]:
    if atr <= 0.0:
        return 0.0, 0.0, 0.0
    di_plus = (plus_smma / atr) * 100.0
    di_minus = (minus_smma / atr) * 100.0
    denominator = di_plus + di_minus
    dx = 0.0 if denominator <= 0.0 else abs(di_plus - di_minus) / denominator * 100.0
    return di_plus, di_minus, dx


def calculate_metaquotes_wilder_batch(
    bars: Sequence[OhlcBar],
    period: int = 8,
) -> tuple[WilderDmiPoint, ...]:
    """Batch reproduction of MetaQuotes' published iADXWilder formula."""
    if period <= 0:
        raise ValueError("DDIX_WILDER_PERIOD_INVALID")
    checked = tuple(_validate_bar(bar) for bar in bars)
    if not checked:
        return tuple()
    raw_tr: list[float | None] = [None]
    raw_plus: list[float | None] = [None]
    raw_minus: list[float | None] = [None]
    for index in range(1, len(checked)):
        tr, plus_dm, minus_dm = _raw_movement(checked[index - 1], checked[index])
        raw_tr.append(tr)
        raw_plus.append(plus_dm)
        raw_minus.append(minus_dm)

    atr: list[float | None] = [None] * len(checked)
    plus_smma: list[float | None] = [None] * len(checked)
    minus_smma: list[float | None] = [None] * len(checked)
    first_smoothed_index = period
    if len(checked) > first_smoothed_index:
        atr[first_smoothed_index] = sum(float(v) for v in raw_tr[1 : period + 1]) / period
        plus_smma[first_smoothed_index] = sum(float(v) for v in raw_plus[1 : period + 1]) / period
        minus_smma[first_smoothed_index] = sum(float(v) for v in raw_minus[1 : period + 1]) / period
        for index in range(first_smoothed_index + 1, len(checked)):
            atr[index] = _smma_step(float(atr[index - 1]), float(raw_tr[index]), period)
            plus_smma[index] = _smma_step(float(plus_smma[index - 1]), float(raw_plus[index]), period)
            minus_smma[index] = _smma_step(float(minus_smma[index - 1]), float(raw_minus[index]), period)

    di_plus: list[float | None] = [None] * len(checked)
    di_minus: list[float | None] = [None] * len(checked)
    dx: list[float | None] = [None] * len(checked)
    for index in range(first_smoothed_index, len(checked)):
        if atr[index] is None:
            continue
        plus_value, minus_value, dx_value = _ratios(
            float(atr[index]),
            float(plus_smma[index]),
            float(minus_smma[index]),
        )
        di_plus[index] = plus_value
        di_minus[index] = minus_value
        dx[index] = dx_value

    adx: list[float | None] = [None] * len(checked)
    first_adx_index = (period * 2) - 1
    if len(checked) > first_adx_index:
        seed = [float(dx[index]) for index in range(period, first_adx_index + 1)]
        adx[first_adx_index] = sum(seed) / float(period)
        for index in range(first_adx_index + 1, len(checked)):
            adx[index] = _smma_step(float(adx[index - 1]), float(dx[index]), period)

    return tuple(
        WilderDmiPoint(
            index=index,
            tr=raw_tr[index],
            plus_dm=raw_plus[index],
            minus_dm=raw_minus[index],
            atr_smma=atr[index],
            plus_dm_smma=plus_smma[index],
            minus_dm_smma=minus_smma[index],
            di_plus=di_plus[index],
            di_minus=di_minus[index],
            dx=dx[index],
            adx=adx[index],
        )
        for index in range(len(checked))
    )


class WilderDmiStream:
    """Independent bar-by-bar SMMA recurrence for parity testing."""

    def __init__(self, period: int = 8) -> None:
        if period <= 0:
            raise ValueError("DDIX_WILDER_PERIOD_INVALID")
        self.period = int(period)
        self._previous: OhlcBar | None = None
        self._index = -1
        self._seed_tr: list[float] = []
        self._seed_plus: list[float] = []
        self._seed_minus: list[float] = []
        self._seed_dx: list[float] = []
        self._atr: float | None = None
        self._plus_smma: float | None = None
        self._minus_smma: float | None = None
        self._adx: float | None = None

    def update(self, bar: OhlcBar) -> WilderDmiPoint:
        current = _validate_bar(bar)
        self._index += 1
        if self._previous is None:
            self._previous = current
            return WilderDmiPoint(
                index=self._index,
                tr=None,
                plus_dm=None,
                minus_dm=None,
                atr_smma=None,
                plus_dm_smma=None,
                minus_dm_smma=None,
                di_plus=None,
                di_minus=None,
                dx=None,
                adx=None,
            )

        previous = self._previous
        up_move = current.high - previous.high
        down_move = previous.low - current.low
        plus_dm = up_move if up_move > 0.0 else 0.0
        minus_dm = down_move if down_move > 0.0 else 0.0
        tr = max(
            abs(current.high - current.low),
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        self._previous = current

        if self._atr is None:
            self._seed_tr.append(tr)
            self._seed_plus.append(plus_dm)
            self._seed_minus.append(minus_dm)
            if len(self._seed_tr) < self.period:
                return WilderDmiPoint(
                    index=self._index, tr=tr, plus_dm=plus_dm, minus_dm=minus_dm,
                    atr_smma=None, plus_dm_smma=None, minus_dm_smma=None,
                    di_plus=None, di_minus=None, dx=None, adx=None,
                )
            self._atr = sum(self._seed_tr) / float(self.period)
            self._plus_smma = sum(self._seed_plus) / float(self.period)
            self._minus_smma = sum(self._seed_minus) / float(self.period)
        else:
            self._atr = ((self._atr * (self.period - 1)) + tr) / float(self.period)
            self._plus_smma = ((self._plus_smma * (self.period - 1)) + plus_dm) / float(self.period)
            self._minus_smma = ((self._minus_smma * (self.period - 1)) + minus_dm) / float(self.period)

        if self._atr <= 0.0:
            di_plus = di_minus = dx = 0.0
        else:
            di_plus = (self._plus_smma / self._atr) * 100.0
            di_minus = (self._minus_smma / self._atr) * 100.0
            total = di_plus + di_minus
            dx = 0.0 if total <= 0.0 else abs(di_plus - di_minus) / total * 100.0

        if self._adx is None:
            self._seed_dx.append(dx)
            if len(self._seed_dx) == self.period:
                self._adx = sum(self._seed_dx) / float(self.period)
        else:
            self._adx = ((self._adx * (self.period - 1)) + dx) / float(self.period)

        return WilderDmiPoint(
            index=self._index,
            tr=tr,
            plus_dm=plus_dm,
            minus_dm=minus_dm,
            atr_smma=self._atr,
            plus_dm_smma=self._plus_smma,
            minus_dm_smma=self._minus_smma,
            di_plus=di_plus,
            di_minus=di_minus,
            dx=dx,
            adx=self._adx,
        )


def calculate_metaquotes_wilder_streaming(
    bars: Iterable[OhlcBar],
    period: int = 8,
) -> tuple[WilderDmiPoint, ...]:
    engine = WilderDmiStream(period=period)
    return tuple(engine.update(bar) for bar in bars)
