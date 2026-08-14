"""
CYCLE THEORY V111 — FIDELITY PORT
CycleTheoryStateMachine — equivalente às variáveis globais de estado do MQ5
(seção [5] do arquivo original) + ResetCycle()/PanicCloseAll().

Cada instância desta classe é UMA instância de máquina de estados, isolada
por symbol/timeframe (Seção 64 do prompt-mestre). O EA original opera sobre
_Symbol implicitamente; aqui isso vira um parâmetro explícito (`symbol`).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import BotState
from .broker import MockBroker
from .telemetry import CycleTheoryTelemetry, EventType


@dataclass
class CycleState:
    current_state: BotState = BotState.STATE_OFF
    is_system_on: bool = False

    ch_high: float = 0.0
    ch_low: float = 0.0
    mid_line50: float = 0.0
    exp_level: float = 0.0
    super_size: float = 0.0
    channel_height: float = 0.0
    setup_dir: int = 0            # +1 compra | -1 venda | 0 indefinido
    g_sl_ref: float = 0.0

    last_order_time: Optional[datetime] = None
    ref_time_start: Optional[datetime] = None
    is_split_active: bool = False
    be_applied: bool = False
    tr_current_level: int = 0
    last_partial_level: int = 0

    capital_trail_active: bool = False

    dash_status: str = "AGUARDANDO START"
    partial_status: str = "-"


class CycleTheoryStateMachine:
    def __init__(self, symbol: str, magic: int, broker: MockBroker,
                 telemetry: Optional[CycleTheoryTelemetry] = None):
        self.symbol = symbol
        self.magic = magic
        self.broker = broker
        self.telemetry = telemetry or CycleTheoryTelemetry()
        self.state = CycleState()

    def reset_cycle(self, error_msg: str = "") -> None:
        """Equivalente exato a ResetCycle() (linha 478-504 do MQ5).
        Preserva: capital_trail_active é SEMPRE zerado aqui (quirk documentado)."""
        s = self.state
        s.current_state = BotState.STATE_STARTING
        s.setup_dir = 0
        s.g_sl_ref = 0.0
        s.tr_current_level = 0
        s.last_partial_level = 0
        s.be_applied = False
        s.is_split_active = False
        s.capital_trail_active = False  # NÃO alterar — comportamento original
        s.partial_status = "AGUARDANDO"

        # Cancela ordens pendentes do bot (quirk: só por magic, sem símbolo — ver broker.py)
        self.broker.cancel_all_pending_by_magic(self.magic)

        s.dash_status = error_msg if error_msg else "INICIANDO..."
        self.telemetry.emit(EventType.CYCLE_RESET, self.symbol, {"reason": error_msg})

    def panic_close_all(self) -> None:
        """Equivalente a PanicCloseAll() (linha 507-517)."""
        self.broker.close_all_by_magic(self.magic)
        self.reset_cycle()
        self.state.is_system_on = False
        self.state.current_state = BotState.STATE_OFF
        self.state.dash_status = "SISTEMA PARADO (PÂNICO)"
        self.telemetry.emit(EventType.PANIC, self.symbol, {})
