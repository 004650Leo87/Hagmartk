"""Calculation-only MT5 margin evidence for Cycle Theory V111.

This module never sends orders. It only calls MetaTrader5.order_calc_margin
and returns an auditable evidence payload for the fidelity matrix.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class MT5MarginEvidence:
    symbol: str
    volume: float
    ask: float
    margin: float
    account_currency: str | None
    leverage: int | None
    server: str | None
    captured_at_utc: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def capture_buy_margin_evidence(mt5: Any, symbol: str, volume: float = 1.0) -> MT5MarginEvidence:
    """Capture BUY margin calculation only; no trade request is created or sent."""
    if volume <= 0:
        raise ValueError("volume must be > 0")
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    account = mt5.account_info()
    if info is None or tick is None or account is None:
        raise RuntimeError(f"MT5 data unavailable for margin evidence: {mt5.last_error()}")

    ask = float(tick.ask)
    margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, float(volume), ask)
    if margin is None:
        raise RuntimeError(f"MT5 order_calc_margin failed: {mt5.last_error()}")

    return MT5MarginEvidence(
        symbol=symbol,
        volume=float(volume),
        ask=ask,
        margin=float(margin),
        account_currency=getattr(account, "currency", None),
        leverage=getattr(account, "leverage", None),
        server=getattr(account, "server", None),
        captured_at_utc=datetime.now(timezone.utc).isoformat(),
    )
