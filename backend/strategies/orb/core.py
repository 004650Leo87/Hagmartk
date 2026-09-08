from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math
from typing import Iterable, Optional, Sequence
from zoneinfo import ZoneInfo

from .config import DEFAULT_ORB_CONFIG, OrbConfig
from .models import (
    Candle,
    Direction,
    EntryPreflight,
    InstrumentProfile,
    OpeningRange,
    Quote,
    SessionWindow,
    Signal,
    TradeLevels,
)


def _require_aware(dt: datetime, name: str) -> None:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"DATA_ERROR: {name} must be timezone-aware")


def _finite_decimal(value: Decimal, name: str) -> Decimal:
    value = Decimal(value)
    if not value.is_finite():
        raise ValueError(f"DATA_ERROR: {name} must be finite")
    return value


def validate_profile(profile: InstrumentProfile) -> None:
    required_text = {
        "instrument_id": profile.instrument_id,
        "market": profile.market,
        "provider": profile.provider,
        "session_timezone": profile.session_timezone,
        "contract_model": profile.contract_model,
        "account_currency": profile.account_currency,
        "data_resolution": profile.data_resolution,
    }
    for name, value in required_text.items():
        if not str(value).strip():
            raise ValueError(f"INVALID_CONFIG: missing {name}")
    try:
        ZoneInfo(profile.session_timezone)
    except Exception as exc:
        raise ValueError("INVALID_CONFIG: invalid IANA timezone") from exc
    for name in ("tick_size", "quantity_min", "quantity_max", "quantity_step"):
        if _finite_decimal(getattr(profile, name), name) <= 0:
            raise ValueError(f"INVALID_CONFIG: {name} must be > 0")
    if profile.quantity_min > profile.quantity_max:
        raise ValueError("INVALID_CONFIG: quantity_min > quantity_max")
    if profile.contract_model.upper() == "LINEAR" and profile.point_value <= 0:
        raise ValueError("INVALID_CONFIG: linear contract requires point_value > 0")
    if profile.allocated_equity <= 0 or profile.margin_available < 0:
        raise ValueError("INVALID_CONFIG: invalid equity/margin")
    if min(profile.slippage_entry_ticks, profile.slippage_stop_ticks,
           profile.slippage_time_ticks, profile.spread_ticks) < 0:
        raise ValueError("INVALID_CONFIG: negative execution cost ticks")


def _resolve_local_datetime(local_date: date, local_time, tz: ZoneInfo, fold: Optional[int]) -> datetime:
    naive = datetime.combine(local_date, local_time)
    aware0 = naive.replace(tzinfo=tz, fold=0)
    aware1 = naive.replace(tzinfo=tz, fold=1)
    roundtrip0 = aware0.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
    roundtrip1 = aware1.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
    valid0 = roundtrip0 == naive
    valid1 = roundtrip1 == naive
    if not valid0 and not valid1:
        raise ValueError("INVALID_SESSION: nonexistent local time")
    ambiguous = valid0 and valid1 and aware0.utcoffset() != aware1.utcoffset()
    if ambiguous and fold not in (0, 1):
        raise ValueError("INVALID_SESSION: ambiguous local time requires explicit fold")
    return naive.replace(tzinfo=tz, fold=fold or 0)


def resolve_session_window(local_date: date, profile: InstrumentProfile, config: OrbConfig = DEFAULT_ORB_CONFIG) -> SessionWindow:
    validate_profile(profile)
    config.validate()
    if local_date.weekday() not in profile.trading_weekdays or local_date in profile.holidays:
        raise ValueError("SESSION_INELIGIBLE: non-trading day")
    tz = ZoneInfo(profile.session_timezone)
    local_start = _resolve_local_datetime(local_date, profile.session_start_local, tz, profile.session_fold)
    end_time = profile.early_closes.get(local_date, profile.session_end_local)
    end_date = local_date
    if end_time <= profile.session_start_local:
        end_date = local_date + timedelta(days=1)
    local_end = _resolve_local_datetime(end_date, end_time, tz, profile.session_fold)
    t0 = local_start.astimezone(timezone.utc)
    session_end = local_end.astimezone(timezone.utc)
    t60 = t0 + timedelta(minutes=config.entry_cutoff_minutes)
    t120 = t0 + timedelta(minutes=config.force_exit_minutes)
    if session_end < t120:
        raise ValueError("SESSION_INELIGIBLE: known session duration < 120 minutes")
    session_id = f"{profile.provider}:{profile.instrument_id}:{profile.contract_id or '-'}:{t0.isoformat()}"
    return SessionWindow(session_id=session_id, local_date=local_date, t0=t0, session_end=session_end, t60=t60, t120=t120)


def validate_candle(candle: Candle, expected_minutes: int = 5) -> None:
    _require_aware(candle.open_time, "candle.open_time")
    _require_aware(candle.close_time, "candle.close_time")
    if candle.close_time <= candle.open_time:
        raise ValueError("DATA_ERROR: candle interval invalid")
    if candle.close_time - candle.open_time != timedelta(minutes=expected_minutes):
        raise ValueError("DATA_ERROR: candle is not a complete aligned interval")
    o, h, l, c = (_finite_decimal(candle.open, "open"), _finite_decimal(candle.high, "high"),
                  _finite_decimal(candle.low, "low"), _finite_decimal(candle.close, "close"))
    if l > h or not (l <= o <= h) or not (l <= c <= h):
        raise ValueError("DATA_ERROR: invalid OHLC ordering")


def _candle_index(candle: Candle, t0: datetime, tf_minutes: int = 5) -> int:
    _require_aware(t0, "t0")
    delta = candle.open_time.astimezone(timezone.utc) - t0.astimezone(timezone.utc)
    seconds = delta.total_seconds()
    step = tf_minutes * 60
    if seconds < 0 or seconds % step != 0:
        raise ValueError("DATA_ERROR: candle is not anchored on t0")
    return int(seconds // step)


def validate_unique_ordered_candles(candles: Sequence[Candle]) -> None:
    seen = {}
    last = None
    for candle in candles:
        validate_candle(candle)
        key = (candle.open_time, candle.close_time)
        signature = (candle.open, candle.high, candle.low, candle.close)
        if key in seen and seen[key] != signature:
            raise ValueError("DATA_ERROR: conflicting duplicate candle")
        if key in seen:
            continue
        if last is not None and candle.open_time <= last:
            raise ValueError("DATA_ERROR: candles not strictly ordered")
        seen[key] = signature
        last = candle.open_time


def build_opening_range(candles: Sequence[Candle], session: SessionWindow, profile: InstrumentProfile,
                        config: OrbConfig = DEFAULT_ORB_CONFIG) -> OpeningRange:
    validate_profile(profile)
    unique = {}
    for candle in candles:
        validate_candle(candle, config.signal_timeframe_minutes)
        idx = _candle_index(candle, session.t0, config.signal_timeframe_minutes)
        if idx in (0, 1, 2):
            if idx in unique:
                prior = unique[idx]
                if (prior.open, prior.high, prior.low, prior.close) != (candle.open, candle.high, candle.low, candle.close):
                    raise ValueError("DATA_ERROR: conflicting duplicate opening-range candle")
            unique[idx] = candle
    if set(unique) != {0, 1, 2}:
        raise ValueError("DATA_ERROR: opening range requires B_0, B_1 and B_2")
    high = max(unique[i].high for i in (0, 1, 2))
    low = min(unique[i].low for i in (0, 1, 2))
    width = high - low
    if width < profile.tick_size:
        raise ValueError("INVALID_RANGE")
    return OpeningRange(high=high, low=low, width=width,
                        frozen_at=session.t0 + timedelta(minutes=config.opening_range_minutes))


def evaluate_signal(candle: Candle, session: SessionWindow, opening_range: OpeningRange,
                    profile: InstrumentProfile, config: OrbConfig = DEFAULT_ORB_CONFIG) -> Optional[Signal]:
    validate_candle(candle, config.signal_timeframe_minutes)
    k = _candle_index(candle, session.t0, config.signal_timeframe_minutes)
    if k < 3 or k > 10:
        return None
    if candle.close_time >= session.t60:
        return None
    delta = profile.tick_size
    direction = None
    if candle.close >= opening_range.high + delta:
        direction = Direction.LONG
    elif candle.close <= opening_range.low - delta:
        direction = Direction.SHORT
    if direction is None:
        return None
    signal_id = f"{session.session_id}:{k}:{direction.value}"
    return Signal(
        signal_id=signal_id,
        session_id=session.session_id,
        direction=direction,
        candle_open_time=candle.open_time,
        candle_close_time=candle.close_time,
        close=candle.close,
        t_signal=candle.close_time,
    )


def first_signal(candles: Sequence[Candle], session: SessionWindow, opening_range: OpeningRange,
                 profile: InstrumentProfile, config: OrbConfig = DEFAULT_ORB_CONFIG) -> Optional[Signal]:
    for candle in candles:
        sig = evaluate_signal(candle, session, opening_range, profile, config)
        if sig is not None:
            return sig
    return None


def floor_grid(value: Decimal, tick: Decimal, origin: Decimal = Decimal("0")) -> Decimal:
    units = ((value - origin) / tick).to_integral_value(rounding=ROUND_FLOOR)
    return origin + units * tick


def ceil_grid(value: Decimal, tick: Decimal, origin: Decimal = Decimal("0")) -> Decimal:
    units = ((value - origin) / tick).to_integral_value(rounding=ROUND_CEILING)
    return origin + units * tick


def fixed_stop(direction: Direction, opening_range: OpeningRange, profile: InstrumentProfile,
               config: OrbConfig = DEFAULT_ORB_CONFIG) -> Decimal:
    buffer = Decimal(config.stop_buffer_ticks) * profile.tick_size
    return opening_range.low - buffer if direction is Direction.LONG else opening_range.high + buffer


def validate_entry_quote(signal: Signal, quote: Quote, session: SessionWindow, stop: Decimal,
                         profile: InstrumentProfile, config: OrbConfig = DEFAULT_ORB_CONFIG) -> None:
    _require_aware(quote.time, "quote.time")
    bid = _finite_decimal(quote.bid, "bid")
    ask = _finite_decimal(quote.ask, "ask")
    if bid > ask:
        raise ValueError("ENTRY_INVALID_QUOTE")
    deadline = min(signal.t_signal + timedelta(milliseconds=config.entry_quote_ttl_ms), session.t60)
    if quote.time < signal.t_signal or quote.time >= deadline:
        raise ValueError("ENTRY_EXPIRED")
    if signal.direction is Direction.LONG and bid <= stop:
        raise ValueError("STOP_ALREADY_BREACHED")
    if signal.direction is Direction.SHORT and ask >= stop:
        raise ValueError("STOP_ALREADY_BREACHED")


def _floor_quantity(value: Decimal, minimum: Decimal, maximum: Decimal, step: Decimal) -> Decimal:
    if value < minimum:
        return Decimal("0")
    capped = min(value, maximum)
    steps = ((capped - minimum) / step).to_integral_value(rounding=ROUND_FLOOR)
    return minimum + steps * step


def linear_profit(direction: Direction, quantity: Decimal, entry: Decimal, exit: Decimal,
                  point_value: Decimal) -> Decimal:
    return direction.sign * quantity * point_value * (exit - entry)


def size_linear_entry(signal: Signal, quote: Quote, session: SessionWindow, opening_range: OpeningRange,
                      profile: InstrumentProfile, config: OrbConfig = DEFAULT_ORB_CONFIG) -> EntryPreflight:
    if profile.contract_model.upper() != "LINEAR":
        raise ValueError("INVALID_CONFIG: non-linear contract requires custom Profit function")
    stop = fixed_stop(signal.direction, opening_range, profile, config)
    validate_entry_quote(signal, quote, session, stop, profile, config)
    delta = profile.tick_size
    if signal.direction is Direction.LONG:
        entry_model = quote.ask + Decimal(profile.slippage_entry_ticks) * delta
        stop_fill = stop - Decimal(profile.slippage_stop_ticks) * delta
    else:
        entry_model = quote.bid - Decimal(profile.slippage_entry_ticks) * delta
        stop_fill = stop + Decimal(profile.slippage_stop_ticks) * delta
    budget = config.risk_fraction * profile.allocated_equity
    per_unit_loss = abs(linear_profit(signal.direction, Decimal("1"), entry_model, stop_fill, profile.point_value))
    per_unit_loss += profile.fees_roundtrip_per_unit
    if per_unit_loss <= 0:
        raise ValueError("INVALID_CONFIG: estimated loss per unit must be positive")
    q_risk = budget / per_unit_loss
    q_margin = profile.margin_available / profile.margin_per_unit if profile.margin_per_unit > 0 else profile.quantity_max
    q = _floor_quantity(min(q_risk, q_margin), profile.quantity_min, profile.quantity_max, profile.quantity_step)
    if q <= 0:
        raise ValueError("MIN_SIZE_EXCEEDS_RISK")
    estimated_loss = q * per_unit_loss
    if estimated_loss > budget:
        raise AssertionError("risk rounding invariant violated")
    return EntryPreflight(
        direction=signal.direction,
        quote=quote,
        stop=stop,
        entry_model=entry_model,
        budget_cash=budget,
        quantity=q,
        estimated_stop_fill=stop_fill,
        estimated_loss_cash=estimated_loss,
    )


def finalize_trade_levels(direction: Direction, quantity: Decimal, entry: Decimal, stop: Decimal,
                          profile: InstrumentProfile, config: OrbConfig = DEFAULT_ORB_CONFIG) -> TradeLevels:
    d = direction.sign
    risk_price = d * (entry - stop)
    if risk_price <= 0:
        raise ValueError("EXECUTION_ABORT: non-positive post-fill risk distance")
    raw_target = entry + d * config.target_r_multiple * risk_price
    if direction is Direction.LONG:
        target = ceil_grid(raw_target, profile.tick_size, profile.grid_origin)
    else:
        target = floor_grid(raw_target, profile.tick_size, profile.grid_origin)
    rr = d * (target - entry) / risk_price
    if rr < config.target_r_multiple:
        raise AssertionError("target rounding moved toward entry")
    risk_cash = abs(linear_profit(direction, quantity, entry, stop, profile.point_value))
    return TradeLevels(
        direction=direction,
        quantity=quantity,
        entry=entry,
        stop=stop,
        risk_price=risk_price,
        target=target,
        rr_effective=rr,
        risk_cash=risk_cash,
    )
