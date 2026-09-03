import pytest

from backend.strategies.hdf.fibonacci_audit import (
    FibonacciAuditStatus, audit_explicit_extension, mirrored_extension_levels,
)


def test_bullish_mirrored_extension_levels():
    levels = mirrored_extension_levels(100.0, 110.0)
    assert levels[0.618] == pytest.approx(116.18)
    assert levels[1.0] == pytest.approx(120.0)
    assert levels[1.618] == pytest.approx(126.18)


def test_bearish_mirrored_extension_levels():
    levels = mirrored_extension_levels(110.0, 100.0)
    assert levels[0.618] == pytest.approx(93.82)
    assert levels[1.0] == pytest.approx(90.0)
    assert levels[2.0] == pytest.approx(80.0)


def test_audit_passes_only_inside_explicit_tolerance():
    ev = audit_explicit_extension(direction="BULLISH", anchor_a=100, anchor_b=110, observed_price=116.20, tolerance=0.03)
    assert ev.status == FibonacciAuditStatus.PASS
    assert ev.matched_level == pytest.approx(0.618)


def test_audit_fails_without_level_contact():
    ev = audit_explicit_extension(direction="BEARISH", anchor_a=110, anchor_b=100, observed_price=96.0, tolerance=0.1)
    assert ev.status == FibonacciAuditStatus.FAIL
    assert ev.matched_level is None


def test_direction_rejects_inverted_anchors():
    with pytest.raises(ValueError):
        audit_explicit_extension(direction="BULLISH", anchor_a=110, anchor_b=100, observed_price=90, tolerance=1)
