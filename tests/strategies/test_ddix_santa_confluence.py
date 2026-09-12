from backend.strategies.ddix.bollinger_reference import (
    BollingerSnapshot,
    classify_bollinger_opening_candidate,
)
from backend.strategies.ddix.dmi_reference import DmiSnapshot, classify_didi_dmi_context
from backend.strategies.ddix.public_reference import (
    MovingAverages3820,
    classify_classic_needle_snapshot,
)
from backend.strategies.ddix.santa_confluence import (
    SantaConfluenceLevel,
    classify_santa_confluence_candidate,
)
from backend.strategies.ddix.stochastic_reference import (
    StochasticPoint,
    classify_stochastic_cross,
)
from backend.strategies.ddix.trix_reference import classify_trix_cross


def _needle(direction="BUY"):
    averages = (
        MovingAverages3820(11.0, 10.0, 9.0)
        if direction == "BUY"
        else MovingAverages3820(9.0, 10.0, 11.0)
    )
    return classify_classic_needle_snapshot(8.0, 12.0, averages)


def _dmi(direction="BUY", rising=True):
    if direction == "BUY":
        prev = DmiSnapshot(40.0, 20.0, 33.0 if rising else 40.0)
        curr = DmiSnapshot(45.0, 15.0, 35.0 if rising else 39.0)
    else:
        prev = DmiSnapshot(20.0, 40.0, 33.0 if rising else 40.0)
        curr = DmiSnapshot(15.0, 45.0, 35.0 if rising else 39.0)
    return classify_didi_dmi_context(prev, curr)


def _bollinger(opening=True):
    previous = BollingerSnapshot(100.0, 1.0, 102.0, 98.0, 4.0, 4.0, 8, 2.0, "TEST")
    current = (
        BollingerSnapshot(100.0, 1.5, 103.0, 97.0, 6.0, 6.0, 8, 2.0, "TEST")
        if opening
        else BollingerSnapshot(100.0, 0.75, 101.5, 98.5, 3.0, 3.0, 8, 2.0, "TEST")
    )
    return classify_bollinger_opening_candidate(previous, current)


def _trix(direction="BUY"):
    if direction == "BUY":
        return classify_trix_cross(0.0, 1.0, 2.0, 1.0)
    return classify_trix_cross(2.0, 1.0, 0.0, 1.0)


def _stochastic(direction="BUY"):
    if direction == "BUY":
        previous = StochasticPoint(1, 35.0, 40.0, "NEUTRAL", "TEST")
        current = StochasticPoint(2, 45.0, 42.0, "NEUTRAL", "TEST")
    else:
        previous = StochasticPoint(1, 65.0, 60.0, "NEUTRAL", "TEST")
        current = StochasticPoint(2, 55.0, 58.0, "NEUTRAL", "TEST")
    return classify_stochastic_cross(previous, current)


def test_full_bullish_alignment_is_semantic_santa_candidate_only():
    evidence = classify_santa_confluence_candidate(
        _needle("BUY"), _dmi("BUY"), _bollinger(True), _trix("BUY"), _stochastic("BUY")
    )
    assert evidence.level is SantaConfluenceLevel.SANTA_CONFLUENCE_CANDIDATE
    assert evidence.semantic_santa_candidate is True
    assert evidence.operationally_approved is False
    assert evidence.direction.value == "BULLISH"
    assert evidence.unresolved_dependencies


def test_full_bearish_alignment_is_symmetric():
    evidence = classify_santa_confluence_candidate(
        _needle("SELL"), _dmi("SELL"), _bollinger(True), _trix("SELL"), _stochastic("SELL")
    )
    assert evidence.semantic_santa_candidate is True
    assert evidence.direction.value == "BEARISH"


def test_primary_context_without_oscillator_alignment_is_not_santa():
    evidence = classify_santa_confluence_candidate(
        _needle("BUY"), _dmi("BUY"), _bollinger(True), _trix("SELL"), _stochastic("BUY")
    )
    assert evidence.level is SantaConfluenceLevel.PRIMARY_CONTEXT_ALIGNED
    assert evidence.semantic_santa_candidate is False
    assert "TRIX_NOT_ALIGNED" in evidence.reason_codes


def test_adx_must_be_accelerating_for_santa_candidate():
    evidence = classify_santa_confluence_candidate(
        _needle("BUY"), _dmi("BUY", rising=False), _bollinger(True), _trix("BUY"), _stochastic("BUY")
    )
    assert evidence.level is SantaConfluenceLevel.PRIMARY_CONTEXT_ALIGNED
    assert evidence.semantic_santa_candidate is False
    assert "ADX_NOT_ACCELERATING" in evidence.reason_codes


def test_dmi_mismatch_leaves_only_needle_level():
    evidence = classify_santa_confluence_candidate(
        _needle("BUY"), _dmi("SELL"), _bollinger(True), _trix("BUY"), _stochastic("BUY")
    )
    assert evidence.level is SantaConfluenceLevel.NEEDLE_ONLY
    assert evidence.semantic_santa_candidate is False
    assert "DMI_DIRECTION_NOT_ALIGNED" in evidence.reason_codes


def test_closed_bollinger_blocks_primary_context():
    evidence = classify_santa_confluence_candidate(
        _needle("BUY"), _dmi("BUY"), _bollinger(False), _trix("BUY"), _stochastic("BUY")
    )
    assert evidence.level is SantaConfluenceLevel.NEEDLE_ONLY
    assert "BOLLINGER_NOT_OPENING" in evidence.reason_codes
