from datetime import datetime, timedelta, timezone
from typing import List
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.domain.events import Direction, StrategyEvent
from backend.indicators.rsi import RSIIndicator
from backend.strategies.hdm_divergence import HDMDivergenceStrategy


def generate_candles_with_divergence(divergence_type: str = "BEARISH") -> pd.DataFrame:
    """Gera dados determinísticos contendo uma divergência clara Nível 1."""
    base_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    closes = [
        100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0,
        110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0, 117.0, 118.0, 119.0,
    ]  # 20 candles de warmup do RSI

    if divergence_type == "BEARISH":
        # P1 na barra 24 (alta 130), queda até barra 30, P2 na barra 36 (alta 135 com RSI menor)
        more = [
            120.0, 125.0, 128.0, 130.0, 127.0, 122.0, 120.0, 118.0, 119.0, 121.0,
            124.0, 128.0, 132.0, 135.0, 131.0, 125.0, 122.0, 120.0, 119.0, 118.0,
        ]
    else:  # BULLISH
        more = [
            110.0, 100.0, 90.0, 80.0, 75.0, 85.0, 95.0, 110.0, 120.0, 125.0,
            115.0, 100.0, 85.0, 70.0, 72.0, 80.0, 90.0, 95.0, 94.0, 93.0,
        ]

    closes.extend(more)

    data = []
    for i, c in enumerate(closes):
        t = base_time + timedelta(minutes=15 * i)
        data.append(
            {
                "time": t.isoformat(),
                "open": c - 0.2,
                "high": c + 0.5,
                "low": c - 0.5,
                "close": c,
                "tick_volume": 100,
                "spread": 1,
                "real_volume": 10,
            }
        )

    return pd.DataFrame(data)


def test_a_b_c_pivot_detection_and_confirmation():
    """PROVA A, B e C: Confirmação de Pivôs sem Lookahead Bias."""
    strategy = HDMDivergenceStrategy(pivot_left=2, pivot_right=2)

    # 5 candles: [10, 12, 15, 11, 10] -> Pivô High no candle 2 (índice 2, valor 15)
    highs = np.array([10.0, 12.0, 15.0, 11.0, 10.0])
    assert strategy._is_pivot_high(highs, 2) is True
    assert strategy._is_pivot_high(highs, 1) is False

    # Pivô Falso (não é maior que os 2 à direita)
    highs_false = np.array([10.0, 12.0, 15.0, 16.0, 10.0])
    assert strategy._is_pivot_high(highs_false, 2) is False

    # Pivô Low: [20, 18, 12, 16, 20] -> Pivô Low no índice 2 (valor 12)
    lows = np.array([20.0, 18.0, 12.0, 16.0, 20.0])
    assert strategy._is_pivot_low(lows, 2) is True


def test_d_and_e_bearish_and_bullish_divergence():
    """PROVA D e E: Detecção precisa de Divergências Nível 1 Baixista e Altista."""
    strategy = HDMDivergenceStrategy(rsi_period=14, pivot_left=2, pivot_right=2)

    # 1. Divergência Baixista
    df_bear = generate_candles_with_divergence("BEARISH")
    events_bear = []
    for i in range(strategy.warmup_bars, len(df_bear)):
        res = strategy.evaluate(df_bear.iloc[: i + 1], "EURUSD", "M15")
        events_bear.extend(res)

    assert len(events_bear) >= 1
    evt = events_bear[0]
    assert evt.direction == Direction.BEARISH
    assert evt.metadata["divergence_type"] == "BEARISH_LEVEL_1"
    assert evt.metadata["pivot_2_price"] > evt.metadata["pivot_1_price"]
    assert evt.metadata["pivot_2_rsi"] < evt.metadata["pivot_1_rsi"]

    # 2. Divergência Altista
    df_bull = generate_candles_with_divergence("BULLISH")
    events_bull = []
    for i in range(strategy.warmup_bars, len(df_bull)):
        res = strategy.evaluate(df_bull.iloc[: i + 1], "EURUSD", "M15")
        events_bull.extend(res)

    bullish_events = [e for e in events_bull if e.direction == Direction.BULLISH]
    assert len(bullish_events) >= 1
    evt_b = bullish_events[0]
    assert evt_b.direction == Direction.BULLISH
    assert evt_b.metadata["divergence_type"] == "BULLISH_LEVEL_1"


def test_f_rsi_warmup_prevents_event():
    """PROVA F: Séries menores que o warmup não geram divergências."""
    strategy = HDMDivergenceStrategy(rsi_period=14)
    df_short = generate_candles_with_divergence("BEARISH").head(15)  # Apenas 15 candles
    res = strategy.evaluate(df_short, "EURUSD", "M15")
    assert res == []


def test_g_distance_constraints_ignored():
    """PROVA G: Pivôs fora da distância mínima/máxima de barras são ignorados."""
    strategy = HDMDivergenceStrategy(min_bars_between_pivots=20, max_bars_between_pivots=30)
    df = generate_candles_with_divergence("BEARISH")
    # A distância no dataset gerado é ~12 barras, portanto menor que min_bars_between_pivots=20
    events = []
    for i in range(strategy.warmup_bars, len(df)):
        res = strategy.evaluate(df.iloc[: i + 1], "EURUSD", "M15")
        events.extend(res)

    assert events == []


def test_h_event_born_at_confirmed_at():
    """PROVA H: O evento nasce estritamente no timestamp confirmed_at (T = pivot_idx + pivot_right)."""
    strategy = HDMDivergenceStrategy(pivot_left=2, pivot_right=2)
    df = generate_candles_with_divergence("BEARISH")

    events = []
    for i in range(strategy.warmup_bars, len(df)):
        res = strategy.evaluate(df.iloc[: i + 1], "EURUSD", "M15")
        if res:
            # O evento é retornado exatamente na iteração do candle i (confirmed_at)
            assert res[0].detected_at == str(df["time"].iloc[i])
            events.extend(res)

    assert len(events) >= 1


def test_i_future_candles_do_not_alter_past_events():
    """PROVA I: Adicionar candles futuros não altera os eventos de divergência já confirmados no passado."""
    strategy = HDMDivergenceStrategy()
    df_base = generate_candles_with_divergence("BEARISH")

    events_base = []
    for i in range(strategy.warmup_bars, len(df_base)):
        res = strategy.evaluate(df_base.iloc[: i + 1], "EURUSD", "M15")
        events_base.extend(res)

    # Estende com candles aleatórios no futuro
    future_data = []
    base_t = datetime.fromisoformat(df_base["time"].iloc[-1])
    for j in range(1, 20):
        future_data.append(
            {
                "time": (base_t + timedelta(minutes=15 * j)).isoformat(),
                "open": 120.0,
                "high": 121.0,
                "low": 119.0,
                "close": 120.0,
                "tick_volume": 100,
                "spread": 1,
                "real_volume": 10,
            }
        )

    df_extended = pd.concat([df_base, pd.DataFrame(future_data)], ignore_index=True)

    events_extended = []
    for i in range(strategy.warmup_bars, len(df_base)):
        res = strategy.evaluate(df_extended.iloc[: i + 1], "EURUSD", "M15")
        events_extended.extend(res)

    assert len(events_base) == len(events_extended)
    assert events_base[0].detected_at == events_extended[0].detected_at


def test_j_no_trade_simulation_activated():
    """PROVA J: Nenhuma operação de trade é gerada nesta etapa (entry_zone/targets vazios)."""
    strategy = HDMDivergenceStrategy()
    df = generate_candles_with_divergence("BEARISH")

    for i in range(strategy.warmup_bars, len(df)):
        res = strategy.evaluate(df.iloc[: i + 1], "EURUSD", "M15")
        for evt in res:
            assert evt.entry_zone == []
            assert evt.invalidation is None
            assert evt.targets == []


def test_divergences_api_endpoint(monkeypatch):
    """Testa o endpoint GET /strategy-lab/divergences/{symbol}."""
    df_bear = generate_candles_with_divergence("BEARISH")

    from backend.api.routes import market
    monkeypatch.setattr(market, "candles", lambda sym, tf, bars, offset: df_bear)

    client = TestClient(app)
    res = client.get("/strategy-lab/divergences/EURUSD?timeframe=M15&bars=50")
    assert res.status_code == 200
    data = res.json()

    assert data["symbol"] == "EURUSD"
    assert data["timeframe"] == "M15"
    assert "events" in data
    assert data["count"] >= 1
    assert data["events"][0]["metadata"]["divergence_type"] == "BEARISH_LEVEL_1"
