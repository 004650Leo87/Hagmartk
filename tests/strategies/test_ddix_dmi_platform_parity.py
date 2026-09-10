import pytest

from backend.strategies.ddix.dmi_platform_parity import (
    PlatformDmiRow,
    compare_platform_rows,
    load_platform_csv,
)
from backend.strategies.ddix.dmi_wilder import OhlcBar, calculate_metaquotes_wilder_batch


def _bars(count=180):
    values = []
    close = 100.0
    for index in range(count):
        move = ((index % 11) - 5) * 0.09 + (0.18 if index % 17 < 9 else -0.14)
        new_close = close + move
        values.append(OhlcBar(max(close, new_close) + 0.4, min(close, new_close) - 0.3, new_close))
        close = new_close
    return tuple(values)


def _platform_rows():
    bars = _bars()
    points = calculate_metaquotes_wilder_batch(bars, period=8)
    rows = []
    for index, (bar, point) in enumerate(zip(bars, points)):
        rows.append(PlatformDmiRow(
            time=f"T{index:03d}", high=bar.high, low=bar.low, close=bar.close,
            adx=point.adx or 0.0, di_plus=point.di_plus or 0.0, di_minus=point.di_minus or 0.0,
        ))
    return tuple(rows)

def test_platform_comparator_accepts_matching_rows_after_warmup():
    report = compare_platform_rows(_platform_rows(), period=8, warmup_bars=128, tolerance=1e-10)
    assert report.passed is True
    assert report.status == "PASS"
    assert report.compared_rows == 52


def test_platform_comparator_exposes_mismatch():
    rows = list(_platform_rows())
    row = rows[-1]
    rows[-1] = PlatformDmiRow(
        time=row.time, high=row.high, low=row.low, close=row.close,
        adx=row.adx + 0.01, di_plus=row.di_plus, di_minus=row.di_minus,
    )
    report = compare_platform_rows(rows, period=8, warmup_bars=128, tolerance=1e-6)
    assert report.passed is False
    assert report.status == "MISMATCH"
    assert report.max_adx_error == pytest.approx(0.01)


def test_platform_csv_loader_parses_probe_shape(tmp_path):
    path = tmp_path / "probe.csv"
    path.write_text(
        "symbol;timeframe;period;time;high;low;close;adx;plus_di;minus_di\n"
        "EURUSDxx;PERIOD_M15;8;2026.09.10 06:00;1.2;1.1;1.15;30;25;15\n",
        encoding="utf-8",
    )
    rows = load_platform_csv(path)
    assert len(rows) == 1
    assert rows[0].adx == pytest.approx(30.0)
    assert rows[0].di_plus == pytest.approx(25.0)
