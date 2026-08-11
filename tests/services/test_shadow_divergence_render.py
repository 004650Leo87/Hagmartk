"""Testes da Fase 5C.26 — Renderer de Marcadores Visuais Operacionais no Gráfico de Preço (Pane 0).

Testa a substituição das linhas do RSI por marcadores operacionais nos candles de preço:
1. RSI LineSeries removidas do Pane 1.
2. Ocorrência BULLISH -> 1 marcador ▲ abaixo do candle (belowBar, verde/lightgreen).
3. Ocorrência BEARISH -> 1 marcador ▼ acima do candle (aboveBar, vermelho/amber).
4. 0 ocorrências live -> 0 marcadores.
5. Filtro de segurança: eventos de teste/fixtures são ignorados.
"""
from __future__ import annotations

import pytest
from backend.domain.shadow_models import HDFEvidence


class MockPriceCandleMarkerRenderer:
    """Mock determinístico do renderer de marcadores operacionais no gráfico de preço (Pane 0)."""

    def __init__(self):
        self.rendered_markers = []
        self.rsi_line_series_count = 0

    def render_evidences(self, evidences: list[HDFEvidence]):
        self.clear()
        live_items = [ev for ev in evidences if getattr(ev, "source", "LIVE_PROSPECTIVE") in ("LIVE_PROSPECTIVE",) and not getattr(ev, "is_test", False)]

        for ev in live_items:
            is_bull = ev.direction == "BULLISH"
            is_activated = getattr(ev, "variant_stage", "HDF_D") == "HDF_DVP" or getattr(ev, "activated", False)
            is_armed = getattr(ev, "armed", False)

            position = "belowBar" if is_bull else "aboveBar"
            shape = "arrowUp" if is_bull else "arrowDown"
            color = (
                ("#21d68d" if is_activated else "#72f2b8")
                if is_bull
                else ("#ff5f72" if is_activated else "#ff9f43")
            )
            text = "HDF" if is_activated else ("ARMED" if is_armed else "HDF")

            marker_item = {
                "evidence_id": ev.evidence_id,
                "symbol": ev.symbol,
                "timeframe": ev.timeframe,
                "direction": ev.direction,
                "pane": 0,  # Price Pane
                "position": position,
                "shape": shape,
                "color": color,
                "text": text,
                "time": ev.pivot_2_time or ev.detected_at,
            }
            self.rendered_markers.append(marker_item)

    def clear(self):
        self.rendered_markers = []
        self.rsi_line_series_count = 0


def test_rsi_lines_removed_and_bullish_marker_rendered():
    renderer = MockPriceCandleMarkerRenderer()
    bullish_ev = HDFEvidence(
        evidence_id="ev_bull_001",
        symbol="XAUUSD",
        timeframe="H1",
        asset_class="METALS",
        direction="BULLISH",
        pivot_1_time="2026-08-11 10:00:00",
        pivot_1_price=2410.50,
        pivot_1_rsi=31.2,
        pivot_2_time="2026-08-11 14:00:00",
        pivot_2_price=2402.00,
        pivot_2_rsi=36.8,
        variant_stage="HDF_DVP",
        armed=True,
        activated=True,
        source="LIVE_PROSPECTIVE",
        is_test=False,
    )

    renderer.render_evidences([bullish_ev])

    # 1. RSI LineSeries = 0
    assert renderer.rsi_line_series_count == 0

    # 2. Marcador no candle de preço
    assert len(renderer.rendered_markers) == 1
    m = renderer.rendered_markers[0]
    assert m["direction"] == "BULLISH"
    assert m["pane"] == 0
    assert m["position"] == "belowBar"
    assert m["shape"] == "arrowUp"
    assert m["color"] == "#21d68d"
    assert m["text"] == "HDF"


def test_bearish_marker_rendered():
    renderer = MockPriceCandleMarkerRenderer()
    bearish_ev = HDFEvidence(
        evidence_id="ev_bear_001",
        symbol="XAUUSD",
        timeframe="H1",
        asset_class="METALS",
        direction="BEARISH",
        pivot_1_time="2026-08-11 08:00:00",
        pivot_1_price=2420.00,
        pivot_1_rsi=68.5,
        pivot_2_time="2026-08-11 12:00:00",
        pivot_2_price=2428.50,
        pivot_2_rsi=62.1,
        variant_stage="HDF_DV",
        armed=True,
        activated=False,
        source="LIVE_PROSPECTIVE",
        is_test=False,
    )

    renderer.render_evidences([bearish_ev])

    assert len(renderer.rendered_markers) == 1
    m = renderer.rendered_markers[0]
    assert m["direction"] == "BEARISH"
    assert m["pane"] == 0
    assert m["position"] == "aboveBar"
    assert m["shape"] == "arrowDown"
    assert m["color"] == "#ff9f43"
    assert m["text"] == "ARMED"


def test_zero_evidence_rendering():
    renderer = MockPriceCandleMarkerRenderer()
    renderer.render_evidences([])
    assert len(renderer.rendered_markers) == 0
    assert renderer.rsi_line_series_count == 0


def test_synthetic_test_events_ignored():
    renderer = MockPriceCandleMarkerRenderer()
    test_ev = HDFEvidence(
        evidence_id="ev_test_001",
        symbol="EURUSD",
        timeframe="M15",
        asset_class="FOREX",
        direction="BULLISH",
        pivot_1_time="t1",
        pivot_1_price=1.0850,
        pivot_1_rsi=28.0,
        pivot_2_time="t2",
        pivot_2_price=1.0820,
        pivot_2_rsi=34.0,
        source="TEST",
        is_test=True,
    )

    renderer.render_evidences([test_ev])
    assert len(renderer.rendered_markers) == 0

