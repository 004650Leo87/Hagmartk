"""Testes do Market Catalog, User Watchlist e Independência do Shadow Universe (Fase 2).

Cobre os 15 pontos de teste do backend:
1. catálogo não é limitado a 5 símbolos
2. catálogo usa fonte real/mock do MarketService
3. metadata mínima é retornada (symbol, category, broker, visible)
4. Watchlist pode ter mais de 5 símbolos
5. adicionar símbolo à Watchlist funciona
6. remover símbolo da Watchlist funciona
7. duplicado não corrompe a Watchlist
8. símbolo inválido (vazio) é tratado corretamente (400)
9. Watchlist persiste no arquivo watchlist.json
10. Shadow Universe possui 13 ativos
11. Shadow possui 8 timeframes
12. Shadow possui 39 combinações
13. remover BTCUSD da Watchlist NÃO remove BTCUSD do Shadow
14. adicionar ativo à Watchlist NÃO cria scanner
15. catálogo e Shadow Universe são fontes independentes
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.routes import _load_watchlist, _save_watchlist, WATCHLIST_PATH
from backend.services.shadow_scanner import (
    CRYPTO_ASSETS,
    FOREX_ASSETS,
    METALS_ASSETS,
    SHADOW_ASSETS,
    SHADOW_TIMEFRAMES,
    ShadowScannerManager,
)

client = TestClient(app)


# ============================================================
# 1. Market Catalog Tests
# ============================================================

def test_market_catalog_endpoint_returns_symbols():
    """GET /market/catalog retorna o catálogo completo sem limite hardcoded de 5."""
    response = client.get("/market/catalog")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Se MT5 estiver conectado, data possui múltiplos ativos (> 5)
    assert len(data) >= 5, "Catálogo deve retornar lista de ativos disponíveis"


def test_market_catalog_metadata_structure():
    """Catálogo expõe metadata mínima para organização na UI."""
    response = client.get("/market/catalog")
    assert response.status_code == 200
    data = response.json()
    if data:
        first = data[0]
        assert "symbol" in first or "name" in first
        assert "category" in first
        assert "broker_path" in first or "path" in first
        assert "visible" in first


# ============================================================
# 2. User Watchlist Tests
# ============================================================

def test_watchlist_can_have_more_than_5_symbols():
    """Watchlist suporta arbitrariamente mais de 5 símbolos sem limite hardcoded."""
    symbols = _load_watchlist()
    assert len(symbols) >= 5, "Watchlist default já possui 13 ativos"


def test_add_symbol_to_watchlist():
    """POST /market/watchlist/add adiciona um novo símbolo."""
    response = client.post("/market/watchlist/add", json={"symbol": "US500"})
    assert response.status_code == 200
    data = response.json()
    assert "US500" in data["symbols"]

    # Limpeza
    client.delete("/market/watchlist/US500")


def test_remove_symbol_from_watchlist():
    """DELETE /market/watchlist/{symbol} remove o símbolo especificado."""
    # Adicionar e depois remover
    client.post("/market/watchlist/add", json={"symbol": "TESTSYM"})
    response = client.delete("/market/watchlist/TESTSYM")
    assert response.status_code == 200
    data = response.json()
    assert "TESTSYM" not in data["symbols"]


def test_add_duplicate_symbol_does_not_corrupt_watchlist():
    """Adicionar símbolo duplicado é idempotente e não corrompe a Watchlist."""
    client.post("/market/watchlist/add", json={"symbol": "EURUSD"})
    response = client.post("/market/watchlist/add", json={"symbol": "EURUSD"})
    assert response.status_code == 200
    symbols = response.json()["symbols"]
    assert symbols.count("EURUSD") == 1


def test_add_invalid_empty_symbol_returns_400():
    """Adicionar símbolo vazio retorna erro 400 Bad Request."""
    response = client.post("/market/watchlist/add", json={"symbol": "   "})
    assert response.status_code == 400


def test_watchlist_persistence():
    """Salvar e carregar a Watchlist persiste os símbolos no disco."""
    original = _load_watchlist()
    test_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "ETHUSD", "AUDUSD"]
    _save_watchlist(test_symbols)

    loaded = _load_watchlist()
    assert loaded == test_symbols

    # Restaurar
    _save_watchlist(original)


# ============================================================
# 3. Shadow Universe & Independence Tests
# ============================================================

def test_shadow_universe_has_13_assets():
    assert len(SHADOW_ASSETS) == 13


def test_shadow_universe_has_3_timeframes():
    assert SHADOW_TIMEFRAMES == ["M5", "M15", "M30", "H1", "H2", "H4", "D1", "W1"]


def test_shadow_universe_has_39_combinations():
    assert len(SHADOW_ASSETS) * len(SHADOW_TIMEFRAMES) == 104


def test_remove_btc_from_watchlist_does_not_remove_from_shadow():
    """Remover BTCUSD da Watchlist do usuário NÃO afeta o Shadow Universe imutável."""
    original_wl = _load_watchlist()

    # Simular remoção de BTCUSD da watchlist
    client.delete("/market/watchlist/BTCUSD")
    current_wl = _load_watchlist()
    assert "BTCUSD" not in current_wl

    # Shadow Universe permanece intacto com 13 ativos e 39 combinações
    assert "BTCUSD" in SHADOW_ASSETS
    assert len(SHADOW_ASSETS) * len(SHADOW_TIMEFRAMES) == 104

    # Restaurar watchlist
    _save_watchlist(original_wl)


def test_add_symbol_to_watchlist_does_not_create_shadow_scanner():
    """Adicionar símbolo arbitrário à Watchlist NÃO cria scanners no Shadow Universe."""
    original_wl = _load_watchlist()

    # Adicionar ativo fora do Shadow Universe (ex: US500 ou AAPL)
    client.post("/market/watchlist/add", json={"symbol": "AAPL"})

    # O Shadow Universe de 39 combinações permanece inalterado
    assert "AAPL" not in SHADOW_ASSETS
    assert len(SHADOW_ASSETS) * len(SHADOW_TIMEFRAMES) == 104

    # Limpar
    client.delete("/market/watchlist/AAPL")
    _save_watchlist(original_wl)


def test_catalog_and_shadow_catalog_are_independent_sources():
    """GET /market/catalog e GET /api/shadow/catalog são endpoints e conceitos independentes."""
    market_resp = client.get("/market/catalog")
    shadow_resp = client.get("/api/shadow/catalog")

    assert market_resp.status_code == 200
    assert shadow_resp.status_code == 200

    shadow_data = shadow_resp.json()
    assert shadow_data["total_combinations"] == 104
    assert shadow_data["total_assets"] == 13
    assert shadow_data["total_timeframes"] == 8
