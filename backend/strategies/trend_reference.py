from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.domain.events import Direction, StrategyEvent
from backend.indicators.atr import ATRIndicator
from backend.strategies.base import BaseStrategy, StrategyRegistry


class HagmartkTrendReferenceStrategy(BaseStrategy):
    """Estratégia de referência mecânica Hagmartk Trend Reference v1.0 (Turtle System 2 simplificado).

    Parâmetros fixos de referência:
    - Entry Lookback = 55 períodos
    - Exit Lookback = 20 períodos
    - ATR / N = 20 períodos (método de Wilder)
    - Stop Inicial = 2N
    - Max Posições Concorrentes = 1 por símbolo
    """

    def __init__(
        self,
        entry_lookback: int = 55,
        exit_lookback: int = 20,
        atr_period: int = 20,
        stop_n_multiplier: float = 2.0,
        allowed_timeframes: Optional[List[str]] = None,
    ) -> None:
        self.strategy_id = "hagmartk_trend_reference"
        self.name = "Hagmartk Trend Reference"
        self.version = "1.0.0"
        self.description = (
            "Estratégia mecânica de referência baseada em Donchian 55/20 e ATR 20 de Wilder "
            "(Turtle System 2 simplificado)."
        )
        # EXPANSÃO DO DOMÍNIO DE TESTE, NÃO ALTERAÇÃO DA REGRA DE TRADING
        self.allowed_timeframes = allowed_timeframes or ["M15", "H1", "H4", "D1"]
        self.max_concurrent_positions_per_symbol = 1

        self.entry_lookback = entry_lookback
        self.exit_lookback = exit_lookback
        self.atr_period = atr_period
        self.stop_n_multiplier = stop_n_multiplier

        self.parameters: Dict[str, Any] = {
            "entry_lookback": entry_lookback,
            "exit_lookback": exit_lookback,
            "atr_period": atr_period,
            "stop_n_multiplier": stop_n_multiplier,
        }

        # 55 candles anteriores + 1 candle T atual = 56 mínimos
        self.minimum_required_bars = entry_lookback + 1
        # Margem recomendada para estabilização da suavização de Wilder no ATR
        self.recommended_warmup_bars = 75
        self.warmup_bars = self.recommended_warmup_bars

        self.atr_indicator = ATRIndicator(period=atr_period)
        self.ambiguous_events_count = 0

    def evaluate(
        self,
        history: pd.DataFrame,
        symbol: str,
        timeframe: str,
        is_closed_bar: bool = True,
    ) -> List[StrategyEvent]:
        if history is None or len(history) < self.minimum_required_bars:
            return []

        # Donchian 55 nos 55 candles estritamente ANTERIORES ao candle T atual
        prior_55 = history.iloc[-self.entry_lookback - 1 : -1]
        upper_55 = float(prior_55["high"].max())
        lower_55 = float(prior_55["low"].min())

        # Cálculo de N_at_entry utilizando estritamente o histórico fechado até T-1 (Zero Lookahead Bias)
        history_t_minus_1 = history.iloc[:-1]
        atr_series = self.atr_indicator.calculate(history_t_minus_1)
        if atr_series.empty or pd.isna(atr_series.iloc[-1]):
            return []
        n_at_entry = float(atr_series.iloc[-1])
        if n_at_entry <= 0.0:
            return []

        candle_t = history.iloc[-1]
        open_t = float(candle_t["open"])
        high_t = float(candle_t["high"])
        low_t = float(candle_t["low"])
        time_t = str(candle_t["time"])

        is_long_breakout = high_t > upper_55
        is_short_breakout = low_t < lower_55

        if not is_long_breakout and not is_short_breakout:
            return []

        # Tratamento de Dual Breakout no mesmo candle T
        if is_long_breakout and is_short_breakout:
            # Caso A: Abertura dentro do canal -> sequência intrabar desconhecida (Ambíguo)
            if lower_55 < open_t < upper_55:
                self.ambiguous_events_count += 1
                return []
            # Caso B: Abertura em Gap além de um dos canais -> Ativação conhecida na abertura
            if open_t > upper_55:
                is_short_breakout = False
            elif open_t < lower_55:
                is_long_breakout = False

        if is_long_breakout:
            entry_price = float(max(upper_55, open_t))
            stop_price = float(entry_price - self.stop_n_multiplier * n_at_entry)
            initial_risk = float(abs(entry_price - stop_price))

            return [
                StrategyEvent(
                    strategy_id=self.strategy_id,
                    strategy_version=self.version,
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=Direction.BULLISH,
                    detected_at=time_t,
                    reference_price=entry_price,
                    entry_zone=[entry_price, entry_price],
                    invalidation=stop_price,
                    targets=[],
                    confidence=1.0,
                    reasons=[f"Donchian 55 Breakout Upper ({upper_55:.5f})"],
                    metadata={
                        "entry_lookback": self.entry_lookback,
                        "exit_lookback": self.exit_lookback,
                        "atr_period": self.atr_period,
                        "n_at_entry": n_at_entry,
                        "initial_stop": stop_price,
                        "breakout_level": upper_55,
                        "initial_risk": initial_risk,
                        "open_at_trigger": open_t,
                    },
                )
            ]

        if is_short_breakout:
            entry_price = float(min(lower_55, open_t))
            stop_price = float(entry_price + self.stop_n_multiplier * n_at_entry)
            initial_risk = float(abs(entry_price - stop_price))

            return [
                StrategyEvent(
                    strategy_id=self.strategy_id,
                    strategy_version=self.version,
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=Direction.BEARISH,
                    detected_at=time_t,
                    reference_price=entry_price,
                    entry_zone=[entry_price, entry_price],
                    invalidation=stop_price,
                    targets=[],
                    confidence=1.0,
                    reasons=[f"Donchian 55 Breakout Lower ({lower_55:.5f})"],
                    metadata={
                        "entry_lookback": self.entry_lookback,
                        "exit_lookback": self.exit_lookback,
                        "atr_period": self.atr_period,
                        "n_at_entry": n_at_entry,
                        "initial_stop": stop_price,
                        "breakout_level": lower_55,
                        "initial_risk": initial_risk,
                        "open_at_trigger": open_t,
                    },
                )
            ]

        return []


# Auto-registro na fábrica global
StrategyRegistry.register(HagmartkTrendReferenceStrategy())
