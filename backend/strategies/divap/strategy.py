from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.domain.events import Direction, StrategyEvent
from backend.indicators.rsi import RSIIndicator
from backend.strategies.base import BaseStrategy, StrategyRegistry
from backend.strategies.divap.detectors import (
    DivergenceDetector,
    PivotDetector,
    ReversalPatternDetector,
    VolumeFilter,
)
from backend.strategies.divap.models import (
    DIVAPOccurrence,
    DIVAPState,
    DIVAPTemporalModel,
    FibonacciAnchorPolicy,
    PivotEqualityPolicy,
    ReversalPatternType,
    VolumeSource,
    classify_forex_session_utc,
)


class DIVAPStrategy(BaseStrategy):
    """Primeira implementação experimental da Estratégia DIVAP (Divergência, Volume, Alvo Fib, Padrão)."""

    def __init__(
        self,
        variant: str = "DIVAP_DVP",
        rsi_period: int = 14,
        pivot_left: int = 2,
        pivot_right: int = 2,
        pivot_equality_policy: PivotEqualityPolicy = PivotEqualityPolicy.STRICT,
        min_bars_between_pivots: int = 5,
        max_bars_between_pivots: int = 50,
        volume_min_relative: float = 1.0,
        execution_buffer: float = 0.0,
        stop_buffer: float = 0.0,
        max_activation_bars: int = 5,
    ) -> None:
        self.variant = variant
        self.strategy_id = f"divap_{variant.lower()}"
        self.name = f"DIVAP Experimental — {variant}"
        self.version = "1.0.0"
        self.description = "Motor de pesquisa experimental DIVAP"
        self.allowed_timeframes = ["M5", "M15", "M30", "H1", "H2", "H4", "D1", "W1"]
        self.max_concurrent_positions_per_symbol = 1

        self.rsi_period = rsi_period
        self.pivot_left = pivot_left
        self.pivot_right = pivot_right
        self.pivot_equality_policy = pivot_equality_policy
        self.min_bars_between_pivots = min_bars_between_pivots
        self.max_bars_between_pivots = max_bars_between_pivots
        self.volume_min_relative = volume_min_relative
        self.execution_buffer = execution_buffer
        self.stop_buffer = stop_buffer
        self.max_activation_bars = max_activation_bars

        self.parameters: Dict[str, Any] = {
            "variant": variant,
            "rsi_period": rsi_period,
            "pivot_left": pivot_left,
            "pivot_right": pivot_right,
            "pivot_equality_policy": pivot_equality_policy.value,
            "min_bars_between_pivots": min_bars_between_pivots,
            "max_bars_between_pivots": max_bars_between_pivots,
            "volume_min_relative": volume_min_relative,
            "execution_buffer": execution_buffer,
            "stop_buffer": stop_buffer,
            "max_activation_bars": max_activation_bars,
        }

        self.minimum_required_bars = rsi_period + max_bars_between_pivots + pivot_right + 5
        self.warmup_bars = self.minimum_required_bars

        self.rsi_indicator = RSIIndicator(period=rsi_period)
        self.pivot_detector = PivotDetector(pivot_left, pivot_right, pivot_equality_policy)
        self.div_detector = DivergenceDetector(min_bars_between_pivots, max_bars_between_pivots)
        self.vol_filter = VolumeFilter(ma_period=20)
        self.pattern_detector = ReversalPatternDetector()

    def evaluate_full_dataset(self, df: pd.DataFrame, symbol: str, timeframe: str) -> List[StrategyEvent]:
        """Avalia um dataset completo em O(N) com vetorização e rastro temporal sem lookahead."""
        if df is None or len(df) < self.minimum_required_bars:
            return []

        rsi_series = self.rsi_indicator.calculate(df)
        if rsi_series.empty:
            return []

        pivot_highs, pivot_lows = self.pivot_detector.find_pivots(df)
        events: List[StrategyEvent] = []

        for curr_idx in range(self.minimum_required_bars, len(df)):
            curr_row = df.iloc[curr_idx]
            curr_time = str(curr_row["time"])

            # 1. Bullish Divergence
            valid_p_lows = [p for p in pivot_lows if p.confirmed_at_index <= curr_idx]
            if len(valid_p_lows) >= 2:
                p1, p2 = valid_p_lows[-2], valid_p_lows[-1]
                if p2.confirmed_at_index == curr_idx:
                    is_bull_div, details = self.div_detector.check_bullish_divergence(p1, p2, rsi_series)
                    if is_bull_div:
                        vol_curr, vol_ma20, rel_vol, vol_bucket = self.vol_filter.evaluate_volume(df, curr_idx)
                        pattern_type, pattern_details = self.pattern_detector.detect_at(df, curr_idx)

                        vol_ok = (rel_vol >= self.volume_min_relative) if ("V" in self.variant) else True
                        pat_ok = (pattern_type == ReversalPatternType.BULLISH_ENGULFING or pattern_type == ReversalPatternType.HAMMER) if ("P" in self.variant) else True

                        if vol_ok and pat_ok:
                            pat_high = pattern_details.get("high", float(curr_row["high"]))
                            pat_low = pattern_details.get("low", float(curr_row["low"]))
                            act_level = float(pat_high + self.execution_buffer)
                            stop_price = float(pat_low - self.stop_buffer)

                            occ = DIVAPOccurrence(
                                occurrence_id=f"divap_{symbol}_{timeframe}_{curr_idx}",
                                symbol=symbol,
                                timeframe=timeframe,
                                direction="BULLISH",
                                state=DIVAPState.CONFLUENCE_COMPLETE,
                                temporal_model=DIVAPTemporalModel(
                                    pivot_1_time=p1.time, pivot_2_time=p2.time,
                                    pivot_1_confirmed_at=p1.confirmed_at_time, pivot_2_confirmed_at=p2.confirmed_at_time,
                                    divergence_detected_at=p2.confirmed_at_time, divergence_confirmed_at=p2.confirmed_at_time,
                                    volume_observed_at=curr_time, reversal_pattern_time=curr_time,
                                    confluence_completed_at=curr_time, armed_at=curr_time, data_available_at_decision=curr_time,
                                ),
                                variant=self.variant,
                                price_p1=p1.price, price_p2=p2.price,
                                rsi_p1=details["rsi_p1"], rsi_p2=details["rsi_p2"],
                                price_delta=details["price_delta"], price_delta_pct=details["price_delta_pct"],
                                rsi_delta=details["rsi_delta"], bars_between_pivots=details["bars_between_pivots"],
                                rsi_extreme_class=details["rsi_extreme_class"],
                                volume_current=vol_curr, volume_ma20=vol_ma20, relative_volume=rel_vol, relative_volume_bucket=vol_bucket,
                                pattern_type=pattern_type, pattern_high=pat_high, pattern_low=pat_low,
                                activation_level=act_level, initial_stop=stop_price, initial_risk=abs(act_level - stop_price),
                                session=classify_forex_session_utc(curr_time),
                            )

                            events.append(
                                StrategyEvent(
                                    strategy_id=self.strategy_id, strategy_version=self.version, symbol=symbol, timeframe=timeframe,
                                    direction=Direction.BULLISH, detected_at=curr_time, reference_price=act_level,
                                    entry_zone=[act_level, act_level], invalidation=stop_price, targets=[], confidence=1.0,
                                    reasons=[f"DIVAP {self.variant} Bullish Div P1={p1.price:.4f} P2={p2.price:.4f}"], metadata=occ.__dict__,
                                )
                            )

            # 2. Bearish Divergence
            valid_p_highs = [p for p in pivot_highs if p.confirmed_at_index <= curr_idx]
            if len(valid_p_highs) >= 2:
                p1, p2 = valid_p_highs[-2], valid_p_highs[-1]
                if p2.confirmed_at_index == curr_idx:
                    is_bear_div, details = self.div_detector.check_bearish_divergence(p1, p2, rsi_series)
                    if is_bear_div:
                        vol_curr, vol_ma20, rel_vol, vol_bucket = self.vol_filter.evaluate_volume(df, curr_idx)
                        pattern_type, pattern_details = self.pattern_detector.detect_at(df, curr_idx)

                        vol_ok = (rel_vol >= self.volume_min_relative) if ("V" in self.variant) else True
                        pat_ok = (pattern_type == ReversalPatternType.BEARISH_ENGULFING or pattern_type == ReversalPatternType.SHOOTING_STAR) if ("P" in self.variant) else True

                        if vol_ok and pat_ok:
                            pat_high = pattern_details.get("high", float(curr_row["high"]))
                            pat_low = pattern_details.get("low", float(curr_row["low"]))
                            act_level = float(pat_low - self.execution_buffer)
                            stop_price = float(pat_high + self.stop_buffer)

                            occ = DIVAPOccurrence(
                                occurrence_id=f"divap_{symbol}_{timeframe}_{curr_idx}",
                                symbol=symbol,
                                timeframe=timeframe,
                                direction="BEARISH",
                                state=DIVAPState.CONFLUENCE_COMPLETE,
                                temporal_model=DIVAPTemporalModel(
                                    pivot_1_time=p1.time, pivot_2_time=p2.time,
                                    pivot_1_confirmed_at=p1.confirmed_at_time, pivot_2_confirmed_at=p2.confirmed_at_time,
                                    divergence_detected_at=p2.confirmed_at_time, divergence_confirmed_at=p2.confirmed_at_time,
                                    volume_observed_at=curr_time, reversal_pattern_time=curr_time,
                                    confluence_completed_at=curr_time, armed_at=curr_time, data_available_at_decision=curr_time,
                                ),
                                variant=self.variant,
                                price_p1=p1.price, price_p2=p2.price,
                                rsi_p1=details["rsi_p1"], rsi_p2=details["rsi_p2"],
                                price_delta=details["price_delta"], price_delta_pct=details["price_delta_pct"],
                                rsi_delta=details["rsi_delta"], bars_between_pivots=details["bars_between_pivots"],
                                rsi_extreme_class=details["rsi_extreme_class"],
                                volume_current=vol_curr, volume_ma20=vol_ma20, relative_volume=rel_vol, relative_volume_bucket=vol_bucket,
                                pattern_type=pattern_type, pattern_high=pat_high, pattern_low=pat_low,
                                activation_level=act_level, initial_stop=stop_price, initial_risk=abs(act_level - stop_price),
                                session=classify_forex_session_utc(curr_time),
                            )

                            events.append(
                                StrategyEvent(
                                    strategy_id=self.strategy_id, strategy_version=self.version, symbol=symbol, timeframe=timeframe,
                                    direction=Direction.BEARISH, detected_at=curr_time, reference_price=act_level,
                                    entry_zone=[act_level, act_level], invalidation=stop_price, targets=[], confidence=1.0,
                                    reasons=[f"DIVAP {self.variant} Bearish Div P1={p1.price:.4f} P2={p2.price:.4f}"], metadata=occ.__dict__,
                                )
                            )

        return events

    def evaluate(self, history: pd.DataFrame, symbol: str, timeframe: str, is_closed_bar: bool = True) -> List[StrategyEvent]:
        # Para compatibilidade com chamadas simples de barra a barra
        return self.evaluate_full_dataset(history, symbol, timeframe)


StrategyRegistry.register(DIVAPStrategy())
