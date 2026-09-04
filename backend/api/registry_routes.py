from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from backend.domain.evidence_contracts import (
    build_product_evidence_registry,
    evidence_contract_to_dict,
)
from backend.domain.market_events import (
    MarketEventClass,
    MarketEventState,
    SHORT_PUBLIC_DISCLAIMER,
    TerminalReason,
)
from backend.domain.strategy_contracts import (
    build_product_strategy_registry,
    strategy_contract_to_dict,
)


router = APIRouter(prefix="/api/registry", tags=["Product Registry"])

_strategy_registry = build_product_strategy_registry()
_evidence_registry = build_product_evidence_registry()


@router.get("/strategies")
def list_product_strategy_contracts() -> Dict[str, Any]:
    contracts = [strategy_contract_to_dict(item) for item in _strategy_registry.list_all()]
    return {"total": len(contracts), "strategies": contracts}


@router.get("/evidence")
def list_product_evidence_contracts() -> Dict[str, Any]:
    contracts = [evidence_contract_to_dict(item) for item in _evidence_registry.list_all()]
    return {"total": len(contracts), "evidence": contracts}


@router.get("/event-protocol")
def get_event_protocol_contract() -> Dict[str, Any]:
    return {
        "event_classes": [item.value for item in MarketEventClass],
        "lifecycle": [item.value for item in MarketEventState],
        "terminal_reasons": [item.value for item in TerminalReason],
        "quant_event_short_disclaimer": SHORT_PUBLIC_DISCLAIMER,
        "publication_adapters_enabled": False,
        "real_order_execution_enabled": False,
    }
