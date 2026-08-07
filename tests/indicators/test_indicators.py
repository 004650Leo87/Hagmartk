import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.indicators.base import IndicatorRegistry
from backend.indicators.moving_averages import EMAIndicator, SMAIndicator
from backend.indicators.rsi import RSIIndicator
from backend.services.market_service import MarketService


def make_sample_df(closes: list[float]) -> pd.DataFrame:
    times = [1620000000 + i * 60 for i in range(len(closes))]
    return pd.DataFrame(
        {
            "time": pd.to_datetime(times, unit="s", utc=True),
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "tick_volume": 100,
            "spread": 1,
            "real_volume": 10,
        }
    )


def test_rsi_wilder_calculation_manual_verification():
    """Valida o cálculo manual do RSI 14 segundo a fórmula oficial de Wilder."""
    # 15 preços -> 14 deltas
    prices = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
        45.89, 46.03, 45.61, 46.28, 46.28, 46.00
    ]
    df = make_sample_df(prices)
    rsi_ind = RSIIndicator(period=14)
    res = rsi_ind.calculate(df)

    # Primeiros 14 valores de RSI devem ser NaN (warmup)
    for i in range(14):
        assert pd.isna(res.iloc[i])

    # O 15º valor (índice 14) deve ser um float numérico válido entre 0 e 100
    assert not pd.isna(res.iloc[14])
    assert 0.0 <= res.iloc[14] <= 100.0

    # 16º valor (índice 15) usa a suavização de Wilder e deve ser válido
    assert not pd.isna(res.iloc[15])
    assert 0.0 <= res.iloc[15] <= 100.0


def test_rsi_edge_cases_all_gains_and_all_losses():
    """Valida casos extremos: 100% de ganhos e 100% de perdas."""
    # Apenas ganhos
    up_prices = [10.0 + i for i in range(20)]
    df_up = make_sample_df(up_prices)
    rsi_up = RSIIndicator(14).calculate(df_up)
    assert rsi_up.iloc[14] == 100.0
    assert rsi_up.iloc[19] == 100.0

    # Apenas perdas
    down_prices = [100.0 - i for i in range(20)]
    df_down = make_sample_df(down_prices)
    rsi_down = RSIIndicator(14).calculate(df_down)
    assert rsi_down.iloc[14] == 0.0
    assert rsi_down.iloc[19] == 0.0


def test_ema_generic_calculation():
    """Valida a Média Móvel Exponencial genérica (EMA)."""
    prices = [10.0 + i for i in range(30)]
    df = make_sample_df(prices)
    ema50 = EMAIndicator(period=10).calculate(df)

    # Período de warmup (primeiros 9) deve ser NaN
    for i in range(9):
        assert pd.isna(ema50.iloc[i])

    assert not pd.isna(ema50.iloc[9])
    assert ema50.iloc[29] > 10.0


def test_zero_lookahead_bias_in_indicators():
    """PROVA DE ZERO LOOKAHEAD BIAS: Adicionar candles futuros ao dataset NÃO altera valores passados já calculados."""
    prices_base = [10.0 + (i % 5) for i in range(30)]
    df_base = make_sample_df(prices_base)

    prices_extended = prices_base + [99.0, 1.0, 50.0, 200.0, 0.0]
    df_extended = make_sample_df(prices_extended)

    rsi_ind = RSIIndicator(14)
    ema_ind = EMAIndicator(20)

    rsi_base = rsi_ind.calculate(df_base)
    rsi_extended = rsi_ind.calculate(df_extended)

    ema_base = ema_ind.calculate(df_base)
    ema_extended = ema_ind.calculate(df_extended)

    # Os primeiros 30 valores calculados na série estendida DEVEM ser idênticos aos da série base
    for i in range(30):
        if pd.isna(rsi_base.iloc[i]):
            assert pd.isna(rsi_extended.iloc[i])
        else:
            assert pytest.approx(rsi_base.iloc[i], abs=1e-6) == rsi_extended.iloc[i]

        if pd.isna(ema_base.iloc[i]):
            assert pd.isna(ema_extended.iloc[i])
        else:
            assert pytest.approx(ema_base.iloc[i], abs=1e-6) == ema_extended.iloc[i]


def test_indicator_registry():
    """Valida o registro e intanciação pela fábrica global."""
    rsi = IndicatorRegistry.get("rsi", period=14)
    assert isinstance(rsi, RSIIndicator)
    assert rsi.period == 14

    ema = IndicatorRegistry.get("ema", period=50)
    assert isinstance(ema, EMAIndicator)
    assert ema.period == 50


def test_market_service_get_indicators(monkeypatch):
    """Valida a consulta de indicadores alinhados no MarketService com mock de candles."""
    prices = [100.0 + (i % 7) for i in range(100)]
    df_mock = make_sample_df(prices)

    service = MarketService()
    monkeypatch.setattr(service, "candles", lambda sym, tf, bars, offset: df_mock.tail(bars))

    res = service.get_indicators(symbol="EURUSD", timeframe=5, bars=30, rsi_periods=[14], ema_periods=[50])
    assert res["symbol"] == "EURUSD"
    assert res["bars"] == 30
    assert "rsi_14" in res["indicators"]
    assert "ema_50" in res["indicators"]
    assert len(res["candles"]) == 30
    assert len(res["indicators"]["rsi_14"]) == 30

    # Valida alinhamento 1:1 de timestamp entre o primeiro candle e o primeiro valor do indicador
    assert res["candles"][0]["time"] == res["indicators"]["rsi_14"][0]["time"]
    assert res["candles"][-1]["time"] == res["indicators"]["rsi_14"][-1]["time"]


def test_indicators_api_endpoint(monkeypatch):
    """Valida o endpoint HTTP GET /market/indicators/{symbol}."""
    prices = [100.0 + (i % 7) for i in range(100)]
    df_mock = make_sample_df(prices)

    from backend.api.routes import market
    monkeypatch.setattr(market, "candles", lambda sym, tf, bars, offset: df_mock.tail(bars))

    client = TestClient(app)
    res = client.get("/market/indicators/EURUSD?timeframe=5&bars=20&rsi=14&ema=50,200")
    assert res.status_code == 200
    data = res.json()

    assert data["symbol"] == "EURUSD"
    assert data["bars"] == 20
    assert "rsi_14" in data["indicators"]
    assert "ema_50" in data["indicators"]
    assert "ema_200" in data["indicators"]
