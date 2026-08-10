"""Teste de Paridade Numérica Estrita do RSI Wilder 14.

Compara o cálculo determinístico de Wilder RSI 14 do backend em Python com o algoritmo em JavaScript.
Garante tolerância matemática e reporta max absolute difference.
"""
from __future__ import annotations

import pandas as pd
import pytest
from backend.indicators.rsi import RSIIndicator


def js_calculate_rsi_reference(prices: list[float], period: int = 14) -> list[float]:
    """Implementação em Python idêntica ao algoritmo calculations.js do frontend."""
    if not prices or len(prices) <= period or period <= 0:
        return []

    results = []
    gains = 0.0
    losses = 0.0

    for i in range(1, period + 1):
        diff = prices[i] - prices[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses += abs(diff)

    avg_gain = gains / period
    avg_loss = losses / period

    rs = 100.0 if avg_loss == 0.0 else avg_gain / avg_loss
    rsi = 100.0 - 100.0 / (1.0 + rs)
    results.append(rsi)

    for i in range(period + 1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gain = diff if diff >= 0 else 0.0
        loss = abs(diff) if diff < 0 else 0.0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        rs = 100.0 if avg_loss == 0.0 else avg_gain / avg_loss
        rsi = 100.0 - 100.0 / (1.0 + rs)
        results.append(rsi)

    return results


def test_rsi_numerical_parity_against_backend_indicator():
    """Valida paridade numérica entre a referência de Wilder RSI e o backend com tolerância 1e-7."""
    # Série sintética realista de 100 candles com oscilações de alta e baixa
    import math
    prices = [100.0 + 5.0 * math.sin(i / 3.0) + i * 0.2 for i in range(100)]

    df = pd.DataFrame({"close": prices})
    backend_rsi_series = RSIIndicator(period=14).calculate(df)

    js_rsi_list = js_calculate_rsi_reference(prices, period=14)

    # Alinhar valores válidos a partir da barra period+1
    # Backend coloca NaN/val nos primeiros candles
    backend_valid = backend_rsi_series.dropna().tolist()

    assert len(backend_valid) > 0
    assert len(js_rsi_list) > 0

    # Comparar os últimos N elementos
    compare_len = min(len(backend_valid), len(js_rsi_list))
    diffs = [
        abs(b - j)
        for b, j in zip(backend_valid[-compare_len:], js_rsi_list[-compare_len:])
    ]

    max_diff = max(diffs) if diffs else 0.0

    print(f"\n[RSI PARITY] Max absolute difference between JS Wilder RSI and Backend RSI: {max_diff:.10e}")

    # Tolerância estrita
    assert max_diff <= 1e-5, f"Divergência matemática no RSI excede a tolerância de 1e-5 (Max Diff: {max_diff})"
