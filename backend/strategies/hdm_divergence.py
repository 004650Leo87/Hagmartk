from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.domain.events import Direction, StrategyEvent
from backend.indicators.rsi import RSIIndicator
from backend.strategies.base import BaseStrategy, StrategyRegistry


class HDMDivergenceStrategy(BaseStrategy):
    """Implementação de referência do detector de divergências Nível 1 (HDM 0.1.0).

    REQUISITO FUNDAMENTAL: ZERO LOOKAHEAD BIAS.
    A confirmação de um pivô ocorre estritamente no candle `T = pivot_index + pivot_right`.
    NENHUMA operação de trade é gerada nesta etapa (`entry_price=None`, `invalidation=None`, `targets=[]`).
    """

    def __init__(
        self,
        rsi_period: int = 14,
        pivot_left: int = 2,
        pivot_right: int = 2,
        min_bars_between_pivots: int = 5,
        max_bars_between_pivots: int = 50,
        allowed_timeframes: Optional[List[str]] = None,
    ) -> None:
        self.strategy_id = "hdm_divergence_reference"
        self.name = "HDM Divergence Model Reference"
        self.version = "0.1.0"
        self.description = (
            "Detector de divergências Nível 1 entre pivôs consecutivos e RSI 14 (Modelo de referência HDM)."
        )
        self.allowed_timeframes = allowed_timeframes or ["M15", "M30", "H1", "H2", "H4", "D1"]
        self.rsi_period = rsi_period
        self.pivot_left = pivot_left
        self.pivot_right = pivot_right
        self.min_bars_between_pivots = min_bars_between_pivots
        self.max_bars_between_pivots = max_bars_between_pivots

        self.parameters = {
            "rsi_period": rsi_period,
            "pivot_left": pivot_left,
            "pivot_right": pivot_right,
            "min_bars_between_pivots": min_bars_between_pivots,
            "max_bars_between_pivots": max_bars_between_pivots,
        }

        self.warmup_bars = rsi_period + pivot_left + pivot_right + 5
        self.allow_open_candle = False
        self.rsi_calculator = RSIIndicator(period=rsi_period)

    def _is_pivot_high(self, highs: np.ndarray, idx: int) -> bool:
        if idx < self.pivot_left or idx + self.pivot_right >= len(highs):
            return False
        val = highs[idx]
        left_slice = highs[idx - self.pivot_left : idx]
        right_slice = highs[idx + 1 : idx + 1 + self.pivot_right]
        return bool(np.all(val > left_slice) and np.all(val > right_slice))

    def _is_pivot_low(self, lows: np.ndarray, idx: int) -> bool:
        if idx < self.pivot_left or idx + self.pivot_right >= len(lows):
            return False
        val = lows[idx]
        left_slice = lows[idx - self.pivot_left : idx]
        right_slice = lows[idx + 1 : idx + 1 + self.pivot_right]
        return bool(np.all(val < left_slice) and np.all(val < right_slice))

    def evaluate(
        self,
        history: pd.DataFrame,
        symbol: str,
        timeframe: str,
        is_closed_bar: bool = True,
    ) -> List[StrategyEvent]:
        if not is_closed_bar and not self.allow_open_candle:
            return []

        if not self.validate_timeframe(timeframe):
            return []

        n_bars = len(history)
        if n_bars < self.warmup_bars:
            return []

        # Calcula RSI 14 utilizando a Indicator Engine centralizada
        rsi_series = self.rsi_calculator.calculate(history)
        rsi_values = rsi_series.values
        highs = history["high"].values
        lows = history["low"].values
        times = history["time"].values

        current_idx = n_bars - 1
        pivot_candidate_idx = current_idx - self.pivot_right

        if pivot_candidate_idx < self.pivot_left:
            return []

        events: List[StrategyEvent] = []

        # 1. Verifica se o candle no índice pivot_candidate_idx é um Pivot High recém-confirmado no candle atual (current_idx)
        if self._is_pivot_high(highs, pivot_candidate_idx):
            p2_idx = pivot_candidate_idx
            p2_price = float(highs[p2_idx])
            p2_rsi = float(rsi_values[p2_idx])

            # Procura pelo Pivot High anterior válido no histórico
            for p1_idx in range(p2_idx - 1, self.pivot_left - 1, -1):
                dist = p2_idx - p1_idx
                if dist > self.max_bars_between_pivots:
                    break

                if self._is_pivot_high(highs, p1_idx):
                    if dist < self.min_bars_between_pivots:
                        continue

                    p1_price = float(highs[p1_idx])
                    p1_rsi = float(rsi_values[p1_idx])

                    # Verifica se RSI em P1 e P2 são válidos (não nulos nem NaN)
                    if np.isnan(p1_rsi) or np.isnan(p2_rsi):
                        break

                    # Divergência Baixista Nível 1: Preço faz Higher High (P2 > P1) e RSI faz Lower High (R2 < R1)
                    if p2_price > p1_price and p2_rsi < p1_rsi:
                        confirmed_at = str(times[current_idx])
                        p1_time = str(times[p1_idx])
                        p2_time = str(times[p2_idx])

                        evt = StrategyEvent(
                            strategy_id=self.strategy_id,
                            strategy_version=self.version,
                            symbol=symbol,
                            timeframe=timeframe,
                            direction=Direction.BEARISH,
                            detected_at=confirmed_at,
                            reference_price=p2_price,
                            entry_zone=[],  # Nenhuma operação gerada nesta etapa
                            invalidation=None,
                            targets=[],
                            confidence=0.85,
                            reasons=["Preço formou Higher High enquanto RSI 14 formou Lower High."],
                            metadata={
                                "divergence_type": "BEARISH_LEVEL_1",
                                "pivot_1_time": p1_time,
                                "pivot_1_price": p1_price,
                                "pivot_1_rsi": round(p1_rsi, 2),
                                "pivot_2_time": p2_time,
                                "pivot_2_price": p2_price,
                                "pivot_2_rsi": round(p2_rsi, 2),
                                "confirmed_at": confirmed_at,
                                "pivot_left": self.pivot_left,
                                "pivot_right": self.pivot_right,
                                "min_bars_between_pivots": self.min_bars_between_pivots,
                                "max_bars_between_pivots": self.max_bars_between_pivots,
                                "rsi_period": self.rsi_period,
                                "price_line": [
                                    {"time": p1_time, "value": p1_price},
                                    {"time": p2_time, "value": p2_price},
                                ],
                                "rsi_line": [
                                    {"time": p1_time, "value": round(p1_rsi, 2)},
                                    {"time": p2_time, "value": round(p2_rsi, 2)},
                                ],
                            },
                        )
                        events.append(evt)
                    break

        # 2. Verifica se o candle no índice pivot_candidate_idx é um Pivot Low recém-confirmado
        if self._is_pivot_low(lows, pivot_candidate_idx):
            p2_idx = pivot_candidate_idx
            p2_price = float(lows[p2_idx])
            p2_rsi = float(rsi_values[p2_idx])

            for p1_idx in range(p2_idx - 1, self.pivot_left - 1, -1):
                dist = p2_idx - p1_idx
                if dist > self.max_bars_between_pivots:
                    break

                if self._is_pivot_low(lows, p1_idx):
                    if dist < self.min_bars_between_pivots:
                        continue

                    p1_price = float(lows[p1_idx])
                    p1_rsi = float(rsi_values[p1_idx])

                    if np.isnan(p1_rsi) or np.isnan(p2_rsi):
                        break

                    # Divergência Altista Nível 1: Preço faz Lower Low (P2 < P1) e RSI faz Higher Low (R2 > R1)
                    if p2_price < p1_price and p2_rsi > p1_rsi:
                        confirmed_at = str(times[current_idx])
                        p1_time = str(times[p1_idx])
                        p2_time = str(times[p2_idx])

                        evt = StrategyEvent(
                            strategy_id=self.strategy_id,
                            strategy_version=self.version,
                            symbol=symbol,
                            timeframe=timeframe,
                            direction=Direction.BULLISH,
                            detected_at=confirmed_at,
                            reference_price=p2_price,
                            entry_zone=[],
                            invalidation=None,
                            targets=[],
                            confidence=0.85,
                            reasons=["Preço formou Lower Low enquanto RSI 14 formou Higher Low."],
                            metadata={
                                "divergence_type": "BULLISH_LEVEL_1",
                                "symmetry_note": "Regra altista simétrica à regra baixista de referência.",
                                "pivot_1_time": p1_time,
                                "pivot_1_price": p1_price,
                                "pivot_1_rsi": round(p1_rsi, 2),
                                "pivot_2_time": p2_time,
                                "pivot_2_price": p2_price,
                                "pivot_2_rsi": round(p2_rsi, 2),
                                "confirmed_at": confirmed_at,
                                "pivot_left": self.pivot_left,
                                "pivot_right": self.pivot_right,
                                "min_bars_between_pivots": self.min_bars_between_pivots,
                                "max_bars_between_pivots": self.max_bars_between_pivots,
                                "rsi_period": self.rsi_period,
                                "price_line": [
                                    {"time": p1_time, "value": p1_price},
                                    {"time": p2_time, "value": p2_price},
                                ],
                                "rsi_line": [
                                    {"time": p1_time, "value": round(p1_rsi, 2)},
                                    {"time": p2_time, "value": round(p2_rsi, 2)},
                                ],
                            },
                        )
                        events.append(evt)
                    break

        return events


# Registra a estratégia de divergência de referência no repositório de estratégias
StrategyRegistry.register(HDMDivergenceStrategy())
