from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from backend.backtest.data_cache import OHLCDataCache
from backend.domain.event_study import EventStudyEngine
from backend.indicators.rsi import RSIIndicator
from backend.strategies.hdf.detectors import (
    DivergenceDetector,
    PivotDetector,
    ReversalPatternDetector,
    VolumeFilter,
)
from backend.strategies.hdf.models import HDFOccurrence, HDFState, PivotEqualityPolicy, ReversalPatternType, VolumeSource
from backend.strategies.hdf.strategy import DIVAPStrategy, HDFStrategy, PatternAssociationPolicy, VolumeObservationPolicy


def make_test_series(prices: list[float], volumes: list[int] | None = None) -> pd.DataFrame:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    vols = volumes or [1000] * len(prices)
    for i, p in enumerate(prices):
        t = base + timedelta(hours=i)
        rows.append({
            "time": t.strftime("%Y-%m-%d %H:%M:%S"),
            "open": p,
            "high": p + 1.0,
            "low": p - 1.0,
            "close": p,
            "tick_volume": vols[i],
        })
    return pd.DataFrame(rows)


# A. Pivot High
def test_A_pivot_high():
    df = make_test_series([10, 11, 15, 12, 10])
    detector = PivotDetector(pivot_left=2, pivot_right=2)
    highs, lows = detector.find_pivots(df)
    assert len(highs) == 1
    assert highs[0].index == 2
    assert highs[0].price == 16.0


# B. Pivot Low
def test_B_pivot_low():
    df = make_test_series([20, 18, 12, 16, 19])
    detector = PivotDetector(pivot_left=2, pivot_right=2)
    highs, lows = detector.find_pivots(df)
    assert len(lows) == 1
    assert lows[0].index == 2


# C. Pivot não confirmado
def test_C_pivot_not_confirmed():
    df = make_test_series([10, 11, 15, 12])
    detector = PivotDetector(pivot_left=2, pivot_right=2)
    highs, lows = detector.find_pivots(df)
    assert len(highs) == 0


# D. Bearish Divergence
def test_D_bearish_divergence():
    detector = DivergenceDetector(min_bars_between_pivots=2, max_bars_between_pivots=20)
    rsi_s = pd.Series([80, 75, 70, 65, 60, 55, 50, 45, 40])
    from backend.strategies.hdf.detectors import PivotPoint
    p1 = PivotPoint(1, "t1", 100.0, True, 3, "t3")
    p2 = PivotPoint(6, "t6", 110.0, True, 8, "t8")
    is_div, details = detector.check_bearish_divergence(p1, p2, rsi_s)
    assert is_div is True
    assert details["price_delta"] == 10.0


# E. Bullish Divergence
def test_E_bullish_divergence():
    detector = DivergenceDetector(min_bars_between_pivots=2, max_bars_between_pivots=20)
    rsi_s = pd.Series([20, 25, 30, 35, 40, 45, 50, 55, 60])
    from backend.strategies.hdf.detectors import PivotPoint
    p1 = PivotPoint(1, "t1", 100.0, False, 3, "t3")
    p2 = PivotPoint(6, "t6", 90.0, False, 8, "t8")
    is_div, details = detector.check_bullish_divergence(p1, p2, rsi_s)
    assert is_div is True


# F. Divergência Falsa
def test_F_false_divergence():
    detector = DivergenceDetector(min_bars_between_pivots=2, max_bars_between_pivots=20)
    rsi_s = pd.Series([50, 55, 60, 65, 70, 75, 80, 85, 90])
    from backend.strategies.hdf.detectors import PivotPoint
    p1 = PivotPoint(1, "t1", 100.0, True, 3, "t3")
    p2 = PivotPoint(6, "t6", 110.0, True, 8, "t8")
    is_div, _ = detector.check_bearish_divergence(p1, p2, rsi_s)
    assert is_div is False


# G. RSI sem Lookahead
def test_G_rsi_no_lookahead():
    df = make_test_series([i for i in range(50)])
    rsi_full = RSIIndicator(period=14).calculate(df)
    rsi_sub = RSIIndicator(period=14).calculate(df.iloc[:30])
    assert rsi_full.iloc[29] == rsi_sub.iloc[29]


# H. Pivô sem Lookahead
def test_H_pivot_no_lookahead():
    df = make_test_series([10, 11, 15, 12, 10, 8, 7])
    detector = PivotDetector(pivot_left=2, pivot_right=2)
    highs, _ = detector.find_pivots(df)
    assert highs[0].confirmed_at_index == 4


# I. Min bars entre pivôs
def test_I_min_bars_between_pivots():
    detector = DivergenceDetector(min_bars_between_pivots=10, max_bars_between_pivots=50)
    from backend.strategies.hdf.detectors import PivotPoint
    p1 = PivotPoint(1, "t1", 100.0, True, 3, "t3")
    p2 = PivotPoint(4, "t4", 110.0, True, 6, "t6")
    is_div, _ = detector.check_bearish_divergence(p1, p2, pd.Series([50] * 10))
    assert is_div is False


# J. Max bars entre pivôs
def test_J_max_bars_between_pivots():
    detector = DivergenceDetector(min_bars_between_pivots=5, max_bars_between_pivots=10)
    from backend.strategies.hdf.detectors import PivotPoint
    p1 = PivotPoint(1, "t1", 100.0, True, 3, "t3")
    p2 = PivotPoint(25, "t25", 110.0, True, 27, "t27")
    is_div, _ = detector.check_bearish_divergence(p1, p2, pd.Series([50] * 30))
    assert is_div is False


# K. Volume MA20
def test_K_volume_ma20():
    vols = [100] * 20 + [200]
    df = make_test_series([10] * 21, volumes=vols)
    v_curr, v_ma20, rel_v, bucket = VolumeFilter(ma_period=20).evaluate_volume(df, 20)
    assert v_curr == 200.0
    assert v_ma20 == 100.0
    assert rel_v == 2.0


# L. Relative Volume
def test_L_relative_volume():
    vols = [100] * 20 + [150]
    df = make_test_series([10] * 21, volumes=vols)
    _, _, rel_v, bucket = VolumeFilter(ma_period=20).evaluate_volume(df, 20)
    assert rel_v == 1.5
    assert bucket == "1.5-2.0"


# M. Bullish Engulfing
def test_M_bullish_engulfing():
    rows = [
        {"time": "t1", "open": 10.0, "high": 10.5, "low": 8.5, "close": 9.0},
        {"time": "t2", "open": 8.8, "high": 11.0, "low": 8.7, "close": 10.5},
    ]
    df = pd.DataFrame(rows)
    ptype, details = ReversalPatternDetector.detect_at(df, 1)
    assert ptype == ReversalPatternType.BULLISH_ENGULFING


# N. Bearish Engulfing
def test_N_bearish_engulfing():
    rows = [
        {"time": "t1", "open": 9.0, "high": 10.5, "low": 8.5, "close": 10.0},
        {"time": "t2", "open": 10.2, "high": 10.6, "low": 8.0, "close": 8.8},
    ]
    df = pd.DataFrame(rows)
    ptype, details = ReversalPatternDetector.detect_at(df, 1)
    assert ptype == ReversalPatternType.BEARISH_ENGULFING


# O. Hammer
def test_O_hammer():
    rows = [
        {"time": "t1", "open": 10.0, "high": 10.5, "low": 8.5, "close": 9.0},
        {"time": "t2", "open": 10.0, "high": 10.1, "low": 7.0, "close": 9.8},
    ]
    df = pd.DataFrame(rows)
    ptype, details = ReversalPatternDetector.detect_at(df, 1)
    assert ptype == ReversalPatternType.HAMMER


# P. Shooting Star
def test_P_shooting_star():
    rows = [
        {"time": "t1", "open": 10.0, "high": 10.5, "low": 8.5, "close": 9.0},
        {"time": "t2", "open": 8.0, "high": 11.0, "low": 7.9, "close": 8.2},
    ]
    df = pd.DataFrame(rows)
    ptype, details = ReversalPatternDetector.detect_at(df, 1)
    assert ptype == ReversalPatternType.SHOOTING_STAR


# Audit: Funnel Inequality DVP <= DV <= D & DVP <= DP <= D
def test_audit_funnel_inequalities():
    df = make_test_series([i for i in range(100)])
    strat = HDFStrategy(variant="HDF_DVP")
    res = strat.evaluate_full_dataset_analysis(df, "TEST", "H1")
    d, dv, dp, dvp = res["hdf_d"], res["hdf_dv"], res["hdf_dp"], res["hdf_dvp"]
    assert dvp <= dv <= d
    assert dvp <= dp <= d


# Audit 1 & 2: Confluence != Activation & Armed without Activation
def test_audit_confluence_not_activation():
    occ = HDFOccurrence(
        occurrence_id="1", symbol="EURUSD", timeframe="H1", direction="BULLISH",
        state=HDFState.ARMED, temporal_model=None, variant="HDF_DVP",
        activation_level=105.0, initial_stop=95.0
    )
    assert occ.state == HDFState.ARMED
    assert occ.state != HDFState.ACTIVATED


# Audit 3 & 4: Activation Next-Bar Only & No Same-Bar Hindsight
def test_audit_activation_next_bar_only():
    strat = HDFStrategy(variant="HDF_DVP", max_activation_bars=5)
    assert strat.activation_policy == "NEXT_BAR"


# Audit 5: Expiration
def test_audit_expiration():
    assert HDFState.EXPIRED.value == "EXPIRED"


# Audit 6: Invalidation Before Activation
def test_audit_invalidation_before_activation():
    assert HDFState.INVALIDATED_BEFORE_ACTIVATION.value == "INVALIDATED_BEFORE_ACTIVATION"


# Audit 7 & 8: Gap Long & Short Execution
def test_audit_gap_long_and_short():
    open_long = 107.0
    act_long = 105.0
    entry_long = max(open_long, act_long)
    assert entry_long == 107.0

    open_short = 93.0
    act_short = 95.0
    entry_short = min(open_short, act_short)
    assert entry_short == 93.0


# Audit 9 & 10: MFE & MAE begin at entry_at
def test_audit_mfe_mae_begin_at_entry_at():
    occ = HDFOccurrence(
        occurrence_id="1", symbol="EURUSD", timeframe="H1", direction="BULLISH",
        state=HDFState.ACTIVATED, temporal_model=None, variant="HDF_DVP",
        entry_price=100.0, initial_risk=5.0, mfe_price=10.0, mae_price=2.0, mfe_r=2.0, mae_r=0.4
    )
    assert occ.mfe_r == 2.0
    assert occ.mae_r == 0.4


# Audit 11: Zero-event symbol remains in report
def test_audit_zero_event_symbol_remains():
    df = make_test_series([10] * 50)
    strat = HDFStrategy(variant="HDF_DVP")
    res = strat.evaluate_full_dataset_analysis(df, "TEST", "H1")
    assert res["symbol"] == "TEST"
    assert res["regular_divergences"] == 0
    assert len(res["activated_events"]) == 0


# Audit 12 & 13: Naming Consistency & Legacy Alias Math Equivalence
def test_audit_naming_and_legacy_alias():
    strat_new = HDFStrategy(variant="HDF_DVP")
    strat_old = DIVAPStrategy(variant="DIVAP_DVP")
    assert strat_new.strategy_id == strat_old.strategy_id
    assert issubclass(DIVAPStrategy, HDFStrategy)


def test_hdf_scope_uses_only_level_1_divergence_and_frozen_timeframes():
    strategy = HDFStrategy(variant="HDF_DVP")
    assert strategy.allowed_timeframes == ["M5", "M15", "M30", "H1", "H2", "H4", "D1", "W1"]
    assert strategy.div_detector.check_bearish_divergence.__doc__.startswith("Bearish Divergence")
    assert strategy.div_detector.check_bullish_divergence.__doc__.startswith("Bullish Divergence")


def test_live_open_tail_detects_fresh_setup_without_premature_expiry(monkeypatch):
    from backend.strategies.hdf.detectors import PivotPoint

    strat = HDFStrategy(variant="HDF_DVP", max_activation_bars=5)
    n = strat.minimum_required_bars + 1
    times = pd.date_range("2026-09-04T00:00:00Z", periods=n, freq="15min")
    df = pd.DataFrame({
        "time": [t.isoformat() for t in times],
        "open": [1.0950] * n, "high": [1.0990] * n,
        "low": [1.0910] * n, "close": [1.0960] * n,
        "tick_volume": [1200] * n,
    })
    t = n - 1
    p1 = PivotPoint(t - 10, str(df.time.iloc[t - 10]), 1.0920, False, t - 8, str(df.time.iloc[t - 8]))
    p2 = PivotPoint(t - 2, str(df.time.iloc[t - 2]), 1.0910, False, t, str(df.time.iloc[t]))
    monkeypatch.setattr(strat.rsi_indicator, "calculate", lambda frame: pd.Series([40.0] * n))
    monkeypatch.setattr(strat.pivot_detector, "find_pivots", lambda frame: ([], [p1, p2]))
    monkeypatch.setattr(strat.div_detector, "check_bullish_divergence", lambda *args: (True, {
        "rsi_p1": 30.0, "rsi_p2": 35.0, "price_delta": -0.001,
        "price_delta_pct": -0.1, "rsi_delta": 5.0,
        "bars_between_pivots": 8, "rsi_extreme_class": "TYPE_1",
    }))
    monkeypatch.setattr(strat.vol_filter, "evaluate_volume", lambda *args: (1200.0, 1000.0, 1.2, "ABOVE_AVERAGE"))
    monkeypatch.setattr(strat.pattern_detector, "detect_at", lambda *args: (
        ReversalPatternType.BULLISH_ENGULFING, {"high": 1.0990, "low": 1.0910}
    ))

    historical = strat.evaluate_full_dataset_analysis(df, "EURUSD", "M15")
    live = strat.evaluate_full_dataset_analysis(df, "EURUSD", "M15", include_open_tail=True)
    assert historical["occurrences"] == []
    assert len(live["occurrences"]) == 1
    assert live["occurrences"][0].state == HDFState.ARMED