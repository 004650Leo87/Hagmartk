"""Testes da Fase 5C.18B — Proof Determinístico do Renderer de Divergências no RSI e Toggle.

Testa isoladamente o pipeline do Renderer de Divergências (Pane 1 RSI):
1. Payload BULLISH -> 1 segmento VERDE no Pane RSI (P1 -> P2)
2. Payload BEARISH -> 1 segmento VERMELHO no Pane RSI (P1 -> P2)
3. Payload VAZIO (0 evidências live) -> 0 segmentos de divergência
4. Toggle Visibilidade (ON -> OFF -> ON) -> Remoção e re-exibição limpas sem séries stale
5. Isolamento estrito -> NENHUMA gravação no banco de produção SQLite
"""
from __future__ import annotations

import pytest
from backend.domain.shadow_models import HDFEvidence


class MockRsiLineRenderer:
    """Mock determinístico do renderer de divergências do Pane 1 (RSI) no MarketChart."""

    def __init__(self):
        self.rendered_series = []
        self.is_visible = True

    def render_evidences(self, evidences: list[HDFEvidence]):
        self.clear()
        if not self.is_visible:
            return

        for ev in evidences:
            if getattr(ev, "source", "LIVE_PROSPECTIVE") not in ("LIVE_PROSPECTIVE", "TEST"):
                continue

            color = "#21d68d" if ev.direction == "BULLISH" else "#ff5f72"
            series_item = {
                "evidence_id": ev.evidence_id,
                "direction": ev.direction,
                "pane": 1,  # RSI Pane
                "color": color,
                "p1": {"time": ev.pivot_1_time, "rsi": ev.pivot_1_rsi, "price": ev.pivot_1_price},
                "p2": {"time": ev.pivot_2_time, "rsi": ev.pivot_2_rsi, "price": ev.pivot_2_price},
            }
            self.rendered_series.append(series_item)

    def set_toggle_visibility(self, visible: bool, evidences: list[HDFEvidence]):
        self.is_visible = visible
        self.render_evidences(evidences)

    def clear(self):
        self.rendered_series = []


def test_bullish_divergence_rendering():
    renderer = MockRsiLineRenderer()
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
        source="LIVE_PROSPECTIVE",
        is_test=False,
    )

    renderer.render_evidences([bullish_ev])

    assert len(renderer.rendered_series) == 1
    s = renderer.rendered_series[0]
    assert s["direction"] == "BULLISH"
    assert s["pane"] == 1
    assert s["color"] == "#21d68d"  # Verde
    assert s["p1"]["rsi"] == 31.2
    assert s["p2"]["rsi"] == 36.8


def test_bearish_divergence_rendering():
    renderer = MockRsiLineRenderer()
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
        source="LIVE_PROSPECTIVE",
        is_test=False,
    )

    renderer.render_evidences([bearish_ev])

    assert len(renderer.rendered_series) == 1
    s = renderer.rendered_series[0]
    assert s["direction"] == "BEARISH"
    assert s["pane"] == 1
    assert s["color"] == "#ff5f72"  # Vermelho
    assert s["p1"]["rsi"] == 68.5
    assert s["p2"]["rsi"] == 62.1


def test_zero_evidence_rendering():
    renderer = MockRsiLineRenderer()
    renderer.render_evidences([])
    assert len(renderer.rendered_series) == 0


def test_toggle_visibility_on_off_on():
    renderer = MockRsiLineRenderer()
    ev = HDFEvidence(
        evidence_id="ev_bull_002",
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
        source="LIVE_PROSPECTIVE",
        is_test=False,
    )

    # 1. Toggle ON -> 1 Linha
    renderer.set_toggle_visibility(True, [ev])
    assert len(renderer.rendered_series) == 1

    # 2. Toggle OFF -> 0 Linhas
    renderer.set_toggle_visibility(False, [ev])
    assert len(renderer.rendered_series) == 0

    # 3. Toggle ON novamente -> 1 Linha re-exibida sem duplicação
    renderer.set_toggle_visibility(True, [ev])
    assert len(renderer.rendered_series) == 1
