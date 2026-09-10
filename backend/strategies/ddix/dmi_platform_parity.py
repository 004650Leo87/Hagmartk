from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path
from typing import Iterable, Mapping

from .dmi_wilder import OhlcBar, calculate_metaquotes_wilder_batch


@dataclass(frozen=True)
class PlatformDmiRow:
    time: str
    high: float
    low: float
    close: float
    adx: float
    di_plus: float
    di_minus: float


@dataclass(frozen=True)
class DmiParityReport:
    compared_rows: int
    max_adx_error: float
    max_di_plus_error: float
    max_di_minus_error: float
    tolerance: float
    passed: bool
    status: str

def _number(value: object) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("DDIX_PLATFORM_VALUE_NOT_FINITE")
    return number


def platform_row_from_mapping(row: Mapping[str, object]) -> PlatformDmiRow:
    return PlatformDmiRow(
        time=str(row["time"]),
        high=_number(row["high"]),
        low=_number(row["low"]),
        close=_number(row["close"]),
        adx=_number(row["adx"]),
        di_plus=_number(row["plus_di"]),
        di_minus=_number(row["minus_di"]),
    )


def load_platform_csv(path: str | Path) -> tuple[PlatformDmiRow, ...]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        rows = tuple(platform_row_from_mapping(row) for row in reader)
    if not rows:
        raise ValueError("DDIX_PLATFORM_CSV_EMPTY")
    return rows

def compare_platform_rows(
    rows: Iterable[PlatformDmiRow],
    period: int = 8,
    warmup_bars: int = 128,
    tolerance: float = 1e-6,
) -> DmiParityReport:
    ordered = tuple(rows)
    if period <= 0:
        raise ValueError("DDIX_PLATFORM_PERIOD_INVALID")
    if warmup_bars < (period * 2 - 1):
        raise ValueError("DDIX_PLATFORM_WARMUP_TOO_SHORT")
    if not math.isfinite(float(tolerance)) or tolerance < 0.0:
        raise ValueError("DDIX_PLATFORM_TOLERANCE_INVALID")
    if len(ordered) <= warmup_bars:
        raise ValueError("DDIX_PLATFORM_ROWS_INSUFFICIENT")

    bars = tuple(OhlcBar(row.high, row.low, row.close) for row in ordered)
    calculated = calculate_metaquotes_wilder_batch(bars, period=period)
    adx_errors: list[float] = []
    plus_errors: list[float] = []
    minus_errors: list[float] = []
    for index in range(warmup_bars, len(ordered)):
        point = calculated[index]
        if point.adx is None or point.di_plus is None or point.di_minus is None:
            continue
        row = ordered[index]
        adx_errors.append(abs(point.adx - row.adx))
        plus_errors.append(abs(point.di_plus - row.di_plus))
        minus_errors.append(abs(point.di_minus - row.di_minus))

    if not adx_errors:
        raise ValueError("DDIX_PLATFORM_NO_COMPARABLE_ROWS")
    max_adx = max(adx_errors)
    max_plus = max(plus_errors)
    max_minus = max(minus_errors)
    passed = max(max_adx, max_plus, max_minus) <= tolerance
    return DmiParityReport(
        compared_rows=len(adx_errors),
        max_adx_error=max_adx,
        max_di_plus_error=max_plus,
        max_di_minus_error=max_minus,
        tolerance=float(tolerance),
        passed=passed,
        status="PASS" if passed else "MISMATCH",
    )
