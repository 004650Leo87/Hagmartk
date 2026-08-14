"""
CYCLE THEORY V111 — FIDELITY PORT
CycleTheoryResearchAdapter — orquestra o ciclo equivalente a OnTick() (linhas
1783-1817), preservando a ORDEM EXATA definida como contrato na Seção 59/25
da Source Audit. Também cobre CheckTradeClosure() e CheckPendingCancellation()
(linhas 1271-1356), que fazem parte do ciclo de verificações do OnTick.
"""
from __future__ import annotations

from .enums import BotState, EntryMode, OrderType
from .broker import MockBroker
from .inputs import CycleTheoryInputs
from .state_machine import CycleTheoryStateMachine
from .persistence import CycleTheoryPersistence
from .execution_model import CycleTheoryExecutionModel
from .signal_engine import CycleTheorySignalEngine
from .position_manager import CycleTheoryPositionManager
from .risk_protections import CycleTheoryRiskProtections
from .telemetry import EventType

_LIMIT_MODES = (EntryMode.ENTRY_PULLBACK_0, EntryMode.ENTRY_PULLBACK_25, EntryMode.ENTRY_PULLBACK_50)


class CycleTheoryResearchAdapter:
    def __init__(self, symbol: str, inputs: CycleTheoryInputs, broker: MockBroker,
                 timeframe: str = "M5", terms_accepted: bool = True):
        self.symbol = symbol
        self.inputs = inputs
        self.broker = broker
        self.terms_accepted = terms_accepted

        self.persistence = CycleTheoryPersistence()
        self.sm = CycleTheoryStateMachine(symbol, inputs.magic_num, broker)
        self.exec_model = CycleTheoryExecutionModel(broker, inputs, self.persistence)
        self.signal_engine = CycleTheorySignalEngine(broker, inputs, self.exec_model, timeframe)
        self.position_manager = CycleTheoryPositionManager(broker, inputs, self.persistence)
        self.risk = CycleTheoryRiskProtections(broker, inputs)

    # ---------------- CheckTradeClosure() — linha 1271-1281 ----------------
    def check_trade_closure(self) -> None:
        s = self.sm.state
        if s.last_order_time is not None:
            elapsed = (self.broker.now - s.last_order_time).total_seconds()
            if elapsed < 3:
                return
        if s.current_state == BotState.STATE_TRADING and not self.broker.has_active_trade(
                self.inputs.magic_num, self.symbol):
            self.sm.reset_cycle()

    # ---------------- CheckPendingCancellation() — linha 1286-1356 ----------------
    def check_pending_cancellation(self) -> None:
        s = self.sm.state
        if s.current_state != BotState.STATE_TRADING:
            return
        if not self.broker.pending_orders:
            return
        if self.broker.get_position_by_magic_symbol(self.inputs.magic_num, self.symbol) is not None:
            return
        if self.inputs.entry_mode not in _LIMIT_MODES:
            return

        # busca a primeira ordem do magic, SEM checar símbolo (quirk preservado)
        ordem = self.broker.find_bot_pending_order(self.inputs.magic_num)
        if ordem is None or ordem.price_open == 0:
            return

        alvo_perdido = False
        alvo1 = 0.0
        if ordem.type == OrderType.BUY_LIMIT:
            alvo1 = ordem.price_open + s.super_size
            if self.broker.bid >= alvo1:
                alvo_perdido = True
        elif ordem.type == OrderType.SELL_LIMIT:
            alvo1 = ordem.price_open - s.super_size
            if self.broker.ask <= alvo1:
                alvo_perdido = True

        if alvo_perdido:
            self.broker.cancel_all_pending_by_magic(self.inputs.magic_num)
            self.sm.telemetry.emit(EventType.PULLBACK_MISSED, self.symbol, {"alvo1": alvo1})
            self.sm.reset_cycle("PULLBACK PERDIDO → NOVO CICLO")

    # ---------------- OnTick() — ordem EXATA da Seção 59 ----------------
    def on_tick(self) -> None:
        if not self.terms_accepted or not self.risk.check_time_and_close(self.sm):
            return

        self.risk.check_hard_stop(self.sm)
        if not self.sm.state.is_system_on:
            return

        if self.broker.has_active_trade(self.inputs.magic_num, self.symbol):
            if self.sm.state.current_state != BotState.STATE_TRADING:
                self.sm.state.current_state = BotState.STATE_TRADING
                self.persistence.save_memory(self.sm)

            self.check_pending_cancellation()

            if not self.broker.has_active_trade(self.inputs.magic_num, self.symbol):
                return

            if self.position_manager.manage_partials(self.sm):
                return
            self.position_manager.manage_trailing(self.sm)
            return

        self.check_trade_closure()
        self.risk.manage_capital_trailing(self.sm)
        self.signal_engine.process_signals(self.sm)

    # ---------------- equivalente simplificado a OnInit(): liga o sistema ----------------
    def power_on(self) -> None:
        self.sm.state.is_system_on = True
        self.sm.reset_cycle()
