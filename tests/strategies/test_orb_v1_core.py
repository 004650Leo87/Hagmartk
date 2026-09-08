from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from backend.strategies.orb.config import DEFAULT_ORB_CONFIG, ORB_V1_CONFIG_HASH
from backend.strategies.orb.core import (
    build_opening_range, evaluate_signal, finalize_trade_levels, fixed_stop,
    resolve_session_window, size_linear_entry, validate_entry_quote,
)
from backend.strategies.orb.metrics import summarize_trades
from backend.strategies.orb.models import (
    Candle, Direction, ExecutionMode, InstrumentProfile, PriceSource, Quote, TradeRecord,
)
from backend.strategies.orb.ohlc_reference import resolve_ohlc_exit

UTC = timezone.utc
D = Decimal


def profile(**overrides):
    base = InstrumentProfile(
        instrument_id="FIXTURE", market="TEST", provider="FIXTURE", contract_id="V1",
        session_timezone="UTC", session_start_local=time(9, 0), session_end_local=time(12, 0),
        source_price=PriceSource.BID, tick_size=D("1"), grid_origin=D("0"),
        quantity_min=D("1"), quantity_max=D("100"), quantity_step=D("1"),
        contract_model="LINEAR", point_value=D("1"), account_currency="USD",
        allocated_equity=D("10000"), margin_available=D("100000"), margin_per_unit=D("1"),
        fees_roundtrip_per_unit=D("0"), slippage_entry_ticks=0, slippage_stop_ticks=0,
        slippage_time_ticks=0, spread_ticks=0, execution_mode=ExecutionMode.OHLC_REFERENCE,
        data_resolution="5m", trading_weekdays=(0,1,2,3,4,5,6),
    )
    return replace(base, **overrides)


def c(h, m, o, hi, lo, cl):
    start = datetime(2026, 9, 7, h, m, tzinfo=UTC)
    return Candle(start, start + timedelta(minutes=5), D(str(o)), D(str(hi)), D(str(lo)), D(str(cl)))


def base_session_and_range(p=None):
    p = p or profile()
    session = resolve_session_window(date(2026,9,7), p)
    opening = [
        c(9,0,105,108,100,106),
        c(9,5,106,110,104,109),
        c(9,10,109,109,101,105),
    ]
    rng = build_opening_range(opening, session, p)
    assert rng.high == D("110") and rng.low == D("100")
    return p, session, rng


def test_frozen_identity_hash_and_parameters():
    DEFAULT_ORB_CONFIG.validate()
    assert len(ORB_V1_CONFIG_HASH) == 64
    assert DEFAULT_ORB_CONFIG.strategy_id == "ORB_OPENING_RANGE_15M_5M_2R"
    assert DEFAULT_ORB_CONFIG.risk_fraction == D("0.0025")


def test_A_range_candle_ending_0915_never_signals():
    p, session, rng = base_session_and_range()
    assert evaluate_signal(c(9,10,109,111,101,111), session, rng, p) is None


def test_B_long_fixture_levels_sizing_target_stop():
    p, session, rng = base_session_and_range()
    sig = evaluate_signal(c(9,15,109,112,108,111), session, rng, p)
    assert sig.direction is Direction.LONG
    q = Quote(sig.t_signal, D("112"), D("112"))
    pre = size_linear_entry(sig, q, session, rng, p)
    assert pre.stop == D("99") and pre.quantity == D("1") and pre.budget_cash == D("25")
    levels = finalize_trade_levels(Direction.LONG, pre.quantity, D("112"), pre.stop, p)
    assert (levels.risk_price, levels.target, levels.risk_cash, levels.rr_effective) == (D("13"),D("138"),D("13"),D("2"))


def test_C_short_fixture():
    p, session, rng = base_session_and_range()
    sig = evaluate_signal(c(9,15,100,101,98,99), session, rng, p)
    assert sig.direction is Direction.SHORT
    levels = finalize_trade_levels(Direction.SHORT, D("1"), D("98"), fixed_stop(Direction.SHORT,rng,p), p)
    assert levels.stop == D("111") and levels.risk_price == D("13") and levels.target == D("72")

@pytest.mark.parametrize("close", [110,100])
def test_D_boundary_close_is_not_signal(close):
    p, session, rng = base_session_and_range()
    candle = c(9,15,105,111,99,close)
    assert evaluate_signal(candle, session, rng, p) is None


def test_E_wick_only_is_not_signal():
    p, session, rng = base_session_and_range()
    assert evaluate_signal(c(9,15,105,112,104,109), session, rng, p) is None


def test_F_0955_eligible_1000_ineligible():
    p, session, rng = base_session_and_range()
    assert evaluate_signal(c(9,50,109,112,108,111), session, rng, p) is not None
    assert evaluate_signal(c(9,55,109,112,108,111), session, rng, p) is None


def test_G_quote_exactly_at_ttl_is_expired():
    p, session, rng = base_session_and_range()
    sig = evaluate_signal(c(9,15,109,112,108,111), session, rng, p)
    stop = fixed_stop(Direction.LONG,rng,p)
    with pytest.raises(ValueError, match="ENTRY_EXPIRED"):
        validate_entry_quote(sig, Quote(sig.t_signal+timedelta(milliseconds=5000),D("112"),D("112")), session, stop, p)


def test_H_return_inside_range_remains_valid_and_sizes_two_units():
    p, session, rng = base_session_and_range()
    sig = evaluate_signal(c(9,15,109,112,108,111), session, rng, p)
    pre = size_linear_entry(sig, Quote(sig.t_signal,D("108"),D("108")), session, rng, p)
    levels = finalize_trade_levels(Direction.LONG, pre.quantity, D("108"), pre.stop, p)
    assert pre.quantity == D("2") and levels.stop == D("99") and levels.risk_price == D("9") and levels.target == D("126")


def test_I_stop_already_breached_rejects():
    p, session, rng = base_session_and_range()
    sig = evaluate_signal(c(9,15,109,112,108,111), session, rng, p)
    with pytest.raises(ValueError, match="STOP_ALREADY_BREACHED"):
        size_linear_entry(sig, Quote(sig.t_signal,D("99"),D("100")), session, rng, p)


def test_J_min_size_above_budget_rejects():
    p = profile(quantity_min=D("2"), quantity_step=D("1"))
    p, session, rng = base_session_and_range(p)
    sig = evaluate_signal(c(9,15,109,112,108,111), session, rng, p)
    with pytest.raises(ValueError, match="MIN_SIZE_EXCEEDS_RISK"):
        size_linear_entry(sig, Quote(sig.t_signal,D("112"),D("112")), session, rng, p)


def test_K_missing_range_candle_blocks_session():
    p = profile(); session = resolve_session_window(date(2026,9,7), p)
    with pytest.raises(ValueError, match="opening range requires"):
        build_opening_range([c(9,0,100,101,99,100),c(9,10,100,101,99,100)],session,p)


def test_L_zero_width_range_invalid():
    p = profile(); session = resolve_session_window(date(2026,9,7), p)
    bars=[c(9,0,100,100,100,100),c(9,5,100,100,100,100),c(9,10,100,100,100,100)]
    with pytest.raises(ValueError, match="INVALID_RANGE"):
        build_opening_range(bars,session,p)


def fixture_levels():
    p, session, rng = base_session_and_range()
    levels = finalize_trade_levels(Direction.LONG,D("1"),D("112"),D("99"),p)
    return p, session, levels


def test_M_same_bar_stop_and_target_is_stop_first():
    p, session, levels = fixture_levels()
    out=resolve_ohlc_exit(levels,c(9,20,112,139,98,120),session.t120,p)
    assert out.reason=="STOP" and out.price==D("99") and out.detail=="STOP_FIRST"


def test_N_gap_through_stop_exits_at_open():
    p, session, levels = fixture_levels()
    out=resolve_ohlc_exit(levels,c(9,20,98,120,97,110),session.t120,p)
    assert out.reason=="STOP" and out.price==D("98")


def test_O_gap_beyond_target_fills_at_target_before_later_fall():
    p, session, levels = fixture_levels()
    out=resolve_ohlc_exit(levels,c(9,20,140,141,98,100),session.t120,p)
    assert out.reason=="TARGET" and out.price==D("138")


def test_P_t120_uses_open_and_does_not_look_later():
    p, session, levels = fixture_levels()
    out=resolve_ohlc_exit(levels,c(11,0,120,150,90,130),session.t120,p)
    assert out.reason=="TIME" and out.price==D("120")


def test_Q_fractional_average_fill_rounds_target_away():
    p=profile(); levels=finalize_trade_levels(Direction.LONG,D("10"),D("112.5"),D("99"),p)
    assert levels.risk_price==D("13.5") and levels.target==D("140") and levels.rr_effective>=D("2")


def test_T_costs_are_not_double_counted_in_metrics():
    trade=TradeRecord(Direction.LONG,D("26"),D("2"),D("24"),D("13"),D("24")/D("13"),"TARGET")
    m=summarize_trades([trade])
    assert m["pnl_net_sum"]==D("24") and m["expectancy_R"]==D("24")/D("13")


def test_U_positive_time_exit_is_win_not_target():
    trade=TradeRecord(Direction.LONG,D("5"),D("0"),D("5"),D("10"),D("0.5"),"TIME")
    m=summarize_trades([trade])
    assert m["p_win"]==1.0 and m["p_target"]==0.0


def test_holiday_and_early_close_less_than_120_are_ineligible():
    p=profile(holidays=(date(2026,9,7),))
    with pytest.raises(ValueError, match="non-trading day"):
        resolve_session_window(date(2026,9,7),p)
    p2=profile(early_closes={date(2026,9,7):time(10,30)})
    with pytest.raises(ValueError, match="duration < 120"):
        resolve_session_window(date(2026,9,7),p2)


def test_R_duplicate_signal_restart_and_opposite_signal_do_not_add_entry():
    from backend.strategies.orb.session import OrbSessionStateMachine
    from backend.strategies.orb.models import SessionState
    p, session, rng = base_session_and_range()
    long_sig=evaluate_signal(c(9,15,109,112,108,111),session,rng,p)
    short_sig=evaluate_signal(c(9,20,100,101,98,99),session,rng,p)
    sm=OrbSessionStateMachine(session.session_id)
    sm.begin_range(); sm.freeze_range()
    assert sm.register_signal(long_sig) is True
    assert sm.register_entry_request() is True
    snap=sm.snapshot()
    restored=OrbSessionStateMachine.restore(snap)
    assert restored.register_signal(long_sig) is False
    assert restored.register_signal(short_sig) is False
    assert restored.register_entry_request() is False
    assert restored.opportunity_consumed and restored.entry_request_consumed


def test_partial_fill_is_technical_not_second_entry_request():
    from backend.strategies.orb.session import OrbSessionStateMachine
    p, session, rng=base_session_and_range()
    sig=evaluate_signal(c(9,15,109,112,108,111),session,rng,p)
    sm=OrbSessionStateMachine(session.session_id); sm.begin_range(); sm.freeze_range(); sm.register_signal(sig)
    assert sm.register_entry_request() is True
    sm.register_entry_fill(D("0.5"))
    assert sm.quantity_filled==D("0.5")
    assert sm.register_entry_request() is False


def test_S_data_gap_after_entry_preserves_exposure_and_state():
    from backend.strategies.orb.session import OrbSessionStateMachine
    from backend.strategies.orb.models import SessionState
    p, session, rng=base_session_and_range(); sig=evaluate_signal(c(9,15,109,112,108,111),session,rng,p)
    sm=OrbSessionStateMachine(session.session_id); sm.begin_range(); sm.freeze_range(); sm.register_signal(sig); sm.register_entry_request(); sm.register_entry_fill(D("1"))
    sm.register_data_gap()
    assert sm.state is SessionState.OPEN and sm.quantity_filled==D("1") and sm.data_gap_after_entry


def test_protection_failure_enters_reconcile_not_skipped():
    from backend.strategies.orb.session import OrbSessionStateMachine
    from backend.strategies.orb.models import SessionState
    p, session, rng=base_session_and_range(); sig=evaluate_signal(c(9,15,109,112,108,111),session,rng,p)
    sm=OrbSessionStateMachine(session.session_id); sm.begin_range(); sm.freeze_range(); sm.register_signal(sig); sm.register_entry_request(); sm.register_entry_fill(D("1"))
    sm.protection_failure()
    assert sm.state is SessionState.ERROR_RECONCILE and sm.reconcile_reason=="PROTECTION_FAILURE"


def test_dst_ambiguous_time_requires_explicit_fold():
    p=profile(session_timezone="America/New_York", session_start_local=time(1,30), session_end_local=time(4,0), session_fold=None)
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_session_window(date(2026,11,1),p)


def test_ledger_deduplicates_deterministic_events_and_exports_jsonl():
    from backend.strategies.orb.config import ORB_V1_CONFIG_HASH
    from backend.strategies.orb.ledger import OrbLedger, OrbLedgerEvent, deterministic_event_id
    event_id=deterministic_event_id("session","SIGNAL","one")
    evt=OrbLedgerEvent(event_id,"ORB_OPENING_RANGE_15M_5M_2R","1.0.0",ORB_V1_CONFIG_HASH,"session","FIXTURE","SIGNAL",datetime(2026,9,7,9,20,tzinfo=UTC),{"price":D("111")})
    ledger=OrbLedger()
    assert ledger.append(evt) is True
    assert ledger.append(evt) is False
    assert ledger.to_jsonl().count("\n")==0
    assert '"event_type":"SIGNAL"' in ledger.to_jsonl()
