from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.domain.events import Direction, StrategyEvent
from backend.indicators.rsi import RSIIndicator
from backend.strategies.base import BaseStrategy, StrategyRegistry
from backend.strategies.hdf.detectors import (
    DivergenceDetector,
    PivotDetector,
    ReversalPatternDetector,
    VolumeFilter,
)
from backend.strategies.hdf.models import (
    FibonacciAnchorPolicy,
    ForexSession,
    HDFOccurrence,
    HDFState,
    HDFTemporalModel,
    PivotEqualityPolicy,
    ReversalPatternType,
    VolumeSource,
    classify_forex_session_utc,
)


class VolumeObservationPolicy(Enum):
    CONFLUENCE_CANDLE = "CONFLUENCE_CANDLE"  # EXPERIMENTAL (Padrão)
    PATTERN_CANDLE = "PATTERN_CANDLE"
    SECOND_PIVOT = "SECOND_PIVOT"


class PatternAssociationPolicy(Enum):
    SAME_BAR = "SAME_BAR"  # EXPERIMENTAL (Padrão: padrão no candle da confirmação do pivô 2)
    WITHIN_WINDOW = "WITHIN_WINDOW"


class HDFStrategy(BaseStrategy):
    """Hagmartk Divergence Flow (HDF) — Estratégia de Pesquisa de Divergência e Confluência de Mercado."""

    def __init__(
        self,
        variant: str = "HDF_DVP",
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
        activation_policy: str = "NEXT_BAR",
        volume_observation_policy: VolumeObservationPolicy = VolumeObservationPolicy.CONFLUENCE_CANDLE,
        pattern_association_policy: PatternAssociationPolicy = PatternAssociationPolicy.SAME_BAR,
    ) -> None:
        var_clean = variant.replace("DIVAP_", "HDF_")
        self.variant = var_clean
        self.strategy_id = f"hagmartk_divergence_flow_{var_clean.lower()}"
        self.name = f"Hagmartk Divergence Flow — {var_clean}"
        self.version = "1.0.0"
        self.description = "Motor de pesquisa quantitativa Hagmartk Divergence Flow (HDF)"
        self.allowed_timeframes = ["M15", "H1", "H4", "D1"]
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
        self.activation_policy = activation_policy
        self.volume_observation_policy = volume_observation_policy
        self.pattern_association_policy = pattern_association_policy

        self.parameters: Dict[str, Any] = {
            "variant": var_clean,
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
            "activation_policy": activation_policy,
            "volume_observation_policy": volume_observation_policy.value,
            "pattern_association_policy": pattern_association_policy.value,
            "fibonacci_specification_status": "UNRESOLVED",
        }

        self.minimum_required_bars = rsi_period + max_bars_between_pivots + pivot_right + 5
        self.warmup_bars = self.minimum_required_bars

        self.rsi_indicator = RSIIndicator(period=rsi_period)
        self.pivot_detector = PivotDetector(pivot_left, pivot_right, pivot_equality_policy)
        self.div_detector = DivergenceDetector(min_bars_between_pivots, max_bars_between_pivots)
        self.vol_filter = VolumeFilter(ma_period=20)
        self.pattern_detector = ReversalPatternDetector()

    def evaluate_full_dataset_analysis(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Avalia um dataset completo com funil de formação auditado (D, DV, DP, DVP), auditoria NEXT_BAR,

        e estudo duplo de excursão (RAW MFE/MAE e REALIZABLE MFE/MAE BEFORE STOP).
        """
        if df is None or len(df) < self.minimum_required_bars:
            return {
                "symbol": symbol,
                "bars": len(df) if df is not None else 0,
                "confirmed_pivots": 0,
                "regular_divergences": 0,
                "hdf_d": 0,
                "hdf_dv": 0,
                "hdf_dp": 0,
                "hdf_dvp": 0,
                "occurrences": [],
                "activated_events": [],
            }

        rsi_series = self.rsi_indicator.calculate(df)
        pivot_highs, pivot_lows = self.pivot_detector.find_pivots(df)
        tot_pivots = len(pivot_highs) + len(pivot_lows)

        occurrences: List[HDFOccurrence] = []
        activated_events: List[StrategyEvent] = []

        count_hdf_d = 0
        count_hdf_dv = 0
        count_hdf_dp = 0
        count_hdf_dvp = 0

        n = len(df)
        highs = df["high"].values
        lows = df["low"].values
        opens = df["open"].values
        times = df["time"].values

        for t in range(self.minimum_required_bars, n - self.max_activation_bars):
            t_time = str(times[t])

            # --------------------------------------------------------
            # 1. Checar confluências BULLISH em t
            # --------------------------------------------------------
            valid_p_lows = [p for p in pivot_lows if p.confirmed_at_index <= t]
            if len(valid_p_lows) >= 2:
                p1, p2 = valid_p_lows[-2], valid_p_lows[-1]
                if p2.confirmed_at_index == t:
                    is_bull_div, details = self.div_detector.check_bullish_divergence(p1, p2, rsi_series)
                    if is_bull_div:
                        count_hdf_d += 1
                        vol_curr, vol_ma20, rel_vol, vol_bucket = self.vol_filter.evaluate_volume(df, t)
                        pattern_type, pattern_details = self.pattern_detector.detect_at(df, t)

                        vol_ok = rel_vol >= self.volume_min_relative
                        pat_ok = pattern_type in (ReversalPatternType.BULLISH_ENGULFING, ReversalPatternType.HAMMER)

                        if vol_ok:
                            count_hdf_dv += 1
                        if pat_ok:
                            count_hdf_dp += 1
                        if vol_ok and pat_ok:
                            count_hdf_dvp += 1

                        # Avaliação conforme variante configurada
                        variant_vol_ok = vol_ok if ("V" in self.variant) else True
                        variant_pat_ok = pat_ok if ("P" in self.variant) else True

                        if variant_vol_ok and variant_pat_ok:
                            pat_high = pattern_details.get("high", float(highs[t]))
                            pat_low = pattern_details.get("low", float(lows[t]))
                            act_level = float(pat_high + self.execution_buffer)
                            initial_stop = float(pat_low - self.stop_buffer)

                            temporal = HDFTemporalModel(
                                pivot_1_time=p1.time, pivot_2_time=p2.time,
                                pivot_1_confirmed_at=p1.confirmed_at_time, pivot_2_confirmed_at=p2.confirmed_at_time,
                                divergence_detected_at=p2.confirmed_at_time, divergence_confirmed_at=p2.confirmed_at_time,
                                volume_observed_at=t_time, reversal_pattern_time=t_time,
                                confluence_completed_at=t_time, armed_at=t_time, data_available_at_decision=t_time,
                            )

                            occ = HDFOccurrence(
                                occurrence_id=f"hdf_{symbol}_{timeframe}_{t}",
                                symbol=symbol, timeframe=timeframe, direction="BULLISH",
                                state=HDFState.ARMED, temporal_model=temporal, variant=self.variant,
                                price_p1=p1.price, price_p2=p2.price,
                                rsi_p1=details["rsi_p1"], rsi_p2=details["rsi_p2"],
                                price_delta=details["price_delta"], price_delta_pct=details["price_delta_pct"],
                                rsi_delta=details["rsi_delta"], bars_between_pivots=details["bars_between_pivots"],
                                rsi_extreme_class=details["rsi_extreme_class"],
                                volume_current=vol_curr, volume_ma20=vol_ma20, relative_volume=rel_vol, relative_volume_bucket=vol_bucket,
                                pattern_type=pattern_type, pattern_high=pat_high, pattern_low=pat_low,
                                activation_level=act_level, initial_stop=initial_stop,
                                activation_policy=self.activation_policy,
                                session=classify_forex_session_utc(t_time),
                            )

                            # Simulação estritamente em barras POSTERIORES (k > t) para NEXT_BAR
                            activated = False
                            for k in range(t + 1, min(t + 1 + self.max_activation_bars, n)):
                                # Invalidação pré-ativação
                                if lows[k] < pat_low:
                                    occ.state = HDFState.INVALIDATED_BEFORE_ACTIVATION
                                    break

                                # Ativação por nível atingido
                                if highs[k] >= act_level:
                                    activated = True
                                    entry_price = float(max(opens[k], act_level))  # Trata Gap Long
                                    init_risk = float(abs(entry_price - initial_stop))

                                    occ.state = HDFState.ACTIVATED
                                    occ.entry_price = entry_price
                                    occ.initial_risk = init_risk
                                    occ.bars_to_activation = k - t
                                    occ.temporal_model.entry_at = str(times[k])
                                    occ.temporal_model.activation_time = str(times[k])
                                    occ.metadata["activation_bar_index"] = k

                                    # ---------------------------------------------------
                                    # A) RAW EXCURSION (Sem Stop Loss precoce)
                                    # ---------------------------------------------------
                                    fwd_df = df.iloc[k : min(k + 20, n)]
                                    max_raw = float(fwd_df["high"].max())
                                    min_raw = float(fwd_df["low"].min())
                                    occ.mfe_price = float(max_raw - entry_price)
                                    occ.mae_price = float(entry_price - min_raw)
                                    occ.mfe_pct = float((occ.mfe_price / entry_price) * 100.0) if entry_price > 0 else 0.0
                                    occ.mae_pct = float((occ.mae_price / entry_price) * 100.0) if entry_price > 0 else 0.0
                                    if init_risk > 0.0:
                                        occ.mfe_r = float(occ.mfe_price / init_risk)
                                        occ.mae_r = float(occ.mae_price / init_risk)

                                    # ---------------------------------------------------
                                    # B) REALIZABLE EXCURSION BEFORE STOP (Com Stop Loss Real e Política Conservadora)
                                    # ---------------------------------------------------
                                    stop_hit = False
                                    stop_hit_at = None
                                    realizable_mfe_p = 0.0
                                    realizable_mae_p = 0.0

                                    realizable_windows = {}

                                    for bar_offset in range(min(20, n - k)):
                                        curr_k = k + bar_offset
                                        c_high, c_low = float(highs[curr_k]), float(lows[curr_k])

                                        # Checa se o stop foi atingido neste candle
                                        if c_low <= initial_stop:
                                            stop_hit = True
                                            stop_hit_at = str(times[curr_k])
                                            # Política conservadora: Stop encerra a excursão realizável
                                            mfe_in_bar = float(max(0.0, c_high - entry_price))  # Se target foi atingido na mesma barra antes/durante o stop
                                            realizable_mae_p = float(entry_price - initial_stop)
                                            realizable_mfe_p = max(realizable_mfe_p, mfe_in_bar)
                                            break
                                        else:
                                            mfe_in_bar = float(c_high - entry_price)
                                            mae_in_bar = float(entry_price - c_low)
                                            realizable_mfe_p = max(realizable_mfe_p, mfe_in_bar)
                                            realizable_mae_p = max(realizable_mae_p, mae_in_bar)

                                    mfe_realizable_r = (realizable_mfe_p / init_risk) if init_risk > 0 else 0.0
                                    mae_realizable_r = (realizable_mae_p / init_risk) if init_risk > 0 else 0.0

                                    occ.metadata["stop_hit"] = stop_hit
                                    occ.metadata["stop_hit_at"] = stop_hit_at
                                    occ.metadata["realizable_mfe_r"] = mfe_realizable_r
                                    occ.metadata["realizable_mae_r"] = mae_realizable_r

                                    # Janelas realizáveis (3, 5, 10, 20 barras)
                                    for w in [3, 5, 10, 20]:
                                        w_mfe_r = 0.0
                                        w_stop_hit = False
                                        for offset in range(min(w, n - k)):
                                            ck = k + offset
                                            ch, cl = float(highs[ck]), float(lows[ck])
                                            if cl <= initial_stop:
                                                w_stop_hit = True
                                                w_mfe_r = max(w_mfe_r, (ch - entry_price) / init_risk if init_risk > 0 else 0.0)
                                                break
                                            else:
                                                w_mfe_r = max(w_mfe_r, (ch - entry_price) / init_risk if init_risk > 0 else 0.0)
                                        realizable_windows[f"{w}_bars"] = {"mfe_r": w_mfe_r, "stop_hit": w_stop_hit}

                                    occ.metadata["realizable_windows"] = realizable_windows

                                    activated_events.append(
                                        StrategyEvent(
                                            strategy_id=self.strategy_id, strategy_version=self.version, symbol=symbol, timeframe=timeframe,
                                            direction=Direction.BULLISH, detected_at=str(times[k]), reference_price=entry_price,
                                            entry_zone=[entry_price, entry_price], invalidation=initial_stop, targets=[], confidence=1.0,
                                            reasons=[f"HDF Bullish Activated at {entry_price:.4f}"], metadata=occ.__dict__,
                                        )
                                    )
                                    break

                            if not activated and occ.state == HDFState.ARMED:
                                occ.state = HDFState.EXPIRED

                            occurrences.append(occ)

            # --------------------------------------------------------
            # 2. Checar confluências BEARISH em t
            # --------------------------------------------------------
            valid_p_highs = [p for p in pivot_highs if p.confirmed_at_index <= t]
            if len(valid_p_highs) >= 2:
                p1, p2 = valid_p_highs[-2], valid_p_highs[-1]
                if p2.confirmed_at_index == t:
                    is_bear_div, details = self.div_detector.check_bearish_divergence(p1, p2, rsi_series)
                    if is_bear_div:
                        count_hdf_d += 1
                        vol_curr, vol_ma20, rel_vol, vol_bucket = self.vol_filter.evaluate_volume(df, t)
                        pattern_type, pattern_details = self.pattern_detector.detect_at(df, t)

                        vol_ok = rel_vol >= self.volume_min_relative
                        pat_ok = pattern_type in (ReversalPatternType.BEARISH_ENGULFING, ReversalPatternType.SHOOTING_STAR)

                        if vol_ok:
                            count_hdf_dv += 1
                        if pat_ok:
                            count_hdf_dp += 1
                        if vol_ok and pat_ok:
                            count_hdf_dvp += 1

                        variant_vol_ok = vol_ok if ("V" in self.variant) else True
                        variant_pat_ok = pat_ok if ("P" in self.variant) else True

                        if variant_vol_ok and variant_pat_ok:
                            pat_high = pattern_details.get("high", float(highs[t]))
                            pat_low = pattern_details.get("low", float(lows[t]))
                            act_level = float(pat_low - self.execution_buffer)
                            initial_stop = float(pat_high + self.stop_buffer)

                            temporal = HDFTemporalModel(
                                pivot_1_time=p1.time, pivot_2_time=p2.time,
                                pivot_1_confirmed_at=p1.confirmed_at_time, pivot_2_confirmed_at=p2.confirmed_at_time,
                                divergence_detected_at=p2.confirmed_at_time, divergence_confirmed_at=p2.confirmed_at_time,
                                volume_observed_at=t_time, reversal_pattern_time=t_time,
                                confluence_completed_at=t_time, armed_at=t_time, data_available_at_decision=t_time,
                            )

                            occ = HDFOccurrence(
                                occurrence_id=f"hdf_{symbol}_{timeframe}_{t}",
                                symbol=symbol, timeframe=timeframe, direction="BEARISH",
                                state=HDFState.ARMED, temporal_model=temporal, variant=self.variant,
                                price_p1=p1.price, price_p2=p2.price,
                                rsi_p1=details["rsi_p1"], rsi_p2=details["rsi_p2"],
                                price_delta=details["price_delta"], price_delta_pct=details["price_delta_pct"],
                                rsi_delta=details["rsi_delta"], bars_between_pivots=details["bars_between_pivots"],
                                rsi_extreme_class=details["rsi_extreme_class"],
                                volume_current=vol_curr, volume_ma20=vol_ma20, relative_volume=rel_vol, relative_volume_bucket=vol_bucket,
                                pattern_type=pattern_type, pattern_high=pat_high, pattern_low=pat_low,
                                activation_level=act_level, initial_stop=initial_stop,
                                activation_policy=self.activation_policy,
                                session=classify_forex_session_utc(t_time),
                            )

                            activated = False
                            for k in range(t + 1, min(t + 1 + self.max_activation_bars, n)):
                                if highs[k] > pat_high:
                                    occ.state = HDFState.INVALIDATED_BEFORE_ACTIVATION
                                    break

                                if lows[k] <= act_level:
                                    activated = True
                                    entry_price = float(min(opens[k], act_level))  # Trata Gap Short
                                    init_risk = float(abs(entry_price - initial_stop))

                                    occ.state = HDFState.ACTIVATED
                                    occ.entry_price = entry_price
                                    occ.initial_risk = init_risk
                                    occ.bars_to_activation = k - t
                                    occ.temporal_model.entry_at = str(times[k])
                                    occ.temporal_model.activation_time = str(times[k])
                                    occ.metadata["activation_bar_index"] = k

                                    # RAW EXCURSION
                                    fwd_df = df.iloc[k : min(k + 20, n)]
                                    max_raw = float(fwd_df["high"].max())
                                    min_raw = float(fwd_df["low"].min())
                                    occ.mfe_price = float(entry_price - min_raw)
                                    occ.mae_price = float(max_raw - entry_price)
                                    occ.mfe_pct = float((occ.mfe_price / entry_price) * 100.0) if entry_price > 0 else 0.0
                                    occ.mae_pct = float((occ.mae_price / entry_price) * 100.0) if entry_price > 0 else 0.0
                                    if init_risk > 0.0:
                                        occ.mfe_r = float(occ.mfe_price / init_risk)
                                        occ.mae_r = float(occ.mae_price / init_risk)

                                    # REALIZABLE EXCURSION BEFORE STOP
                                    stop_hit = False
                                    stop_hit_at = None
                                    realizable_mfe_p = 0.0
                                    realizable_mae_p = 0.0
                                    realizable_windows = {}

                                    for bar_offset in range(min(20, n - k)):
                                        curr_k = k + bar_offset
                                        ch, cl = float(highs[curr_k]), float(lows[curr_k])
                                        if ch >= initial_stop:
                                            stop_hit = True
                                            stop_hit_at = str(times[curr_k])
                                            mfe_in_bar = float(max(0.0, entry_price - cl))
                                            realizable_mae_p = float(initial_stop - entry_price)
                                            realizable_mfe_p = max(realizable_mfe_p, mfe_in_bar)
                                            break
                                        else:
                                            mfe_in_bar = float(entry_price - cl)
                                            mae_in_bar = float(ch - entry_price)
                                            realizable_mfe_p = max(realizable_mfe_p, mfe_in_bar)
                                            realizable_mae_p = max(realizable_mae_p, mae_in_bar)

                                    mfe_realizable_r = (realizable_mfe_p / init_risk) if init_risk > 0 else 0.0
                                    mae_realizable_r = (realizable_mae_p / init_risk) if init_risk > 0 else 0.0

                                    occ.metadata["stop_hit"] = stop_hit
                                    occ.metadata["stop_hit_at"] = stop_hit_at
                                    occ.metadata["realizable_mfe_r"] = mfe_realizable_r
                                    occ.metadata["realizable_mae_r"] = mae_realizable_r

                                    for w in [3, 5, 10, 20]:
                                        w_mfe_r = 0.0
                                        w_stop_hit = False
                                        for offset in range(min(w, n - k)):
                                            ck = k + offset
                                            ch, cl = float(highs[ck]), float(lows[ck])
                                            if ch >= initial_stop:
                                                w_stop_hit = True
                                                w_mfe_r = max(w_mfe_r, (entry_price - cl) / init_risk if init_risk > 0 else 0.0)
                                                break
                                            else:
                                                w_mfe_r = max(w_mfe_r, (entry_price - cl) / init_risk if init_risk > 0 else 0.0)
                                        realizable_windows[f"{w}_bars"] = {"mfe_r": w_mfe_r, "stop_hit": w_stop_hit}

                                    occ.metadata["realizable_windows"] = realizable_windows

                                    activated_events.append(
                                        StrategyEvent(
                                            strategy_id=self.strategy_id, strategy_version=self.version, symbol=symbol, timeframe=timeframe,
                                            direction=Direction.BEARISH, detected_at=str(times[k]), reference_price=entry_price,
                                            entry_zone=[entry_price, entry_price], invalidation=initial_stop, targets=[], confidence=1.0,
                                            reasons=[f"HDF Bearish Activated at {entry_price:.4f}"], metadata=occ.__dict__,
                                        )
                                    )
                                    break

                            if not activated and occ.state == HDFState.ARMED:
                                occ.state = HDFState.EXPIRED

                            occurrences.append(occ)

        return {
            "symbol": symbol,
            "bars": n,
            "confirmed_pivots": tot_pivots,
            "regular_divergences": count_hdf_d,
            "hdf_d": count_hdf_d,
            "hdf_dv": count_hdf_dv,
            "hdf_dp": count_hdf_dp,
            "hdf_dvp": count_hdf_dvp,
            "occurrences": occurrences,
            "activated_events": activated_events,
        }

    def evaluate(self, history: pd.DataFrame, symbol: str, timeframe: str, is_closed_bar: bool = True) -> List[StrategyEvent]:
        res = self.evaluate_full_dataset_analysis(history, symbol, timeframe)
        return res["activated_events"]


DIVAPStrategy = HDFStrategy

StrategyRegistry.register(HDFStrategy())
