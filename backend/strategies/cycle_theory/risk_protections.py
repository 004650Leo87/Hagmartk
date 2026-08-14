"""
CYCLE THEORY V111 — FIDELITY PORT
CycleTheoryRiskProtections — equivalente a CheckHardStop(), ManageCapitalTrailing(),
CheckTimeAndClose() (linhas 524-620 do MQ5).
"""
from __future__ import annotations
from datetime import datetime

from .enums import BotState
from .broker import MockBroker
from .inputs import CycleTheoryInputs
from .state_machine import CycleTheoryStateMachine
from .telemetry import EventType


def _time_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class CycleTheoryRiskProtections:
    def __init__(self, broker: MockBroker, inputs: CycleTheoryInputs):
        self.broker = broker
        self.inputs = inputs

    def _day_start(self) -> datetime:
        return self.broker.now.replace(hour=0, minute=0, second=0, microsecond=0)

    def _daily_profit(self) -> float:
        p, _, _ = self.broker.period_stats(self._day_start(), self.inputs.magic_num)
        return p

    # ---------------- CheckHardStop() ----------------
    def check_hard_stop(self, sm: CycleTheoryStateMachine) -> None:
        s = sm.state
        if s.current_state == BotState.STATE_OFF:
            return

        total = self._daily_profit() + self.broker.floating_profit(self.inputs.magic_num)

        if self.inputs.max_daily_loss > 0 and total <= -self.inputs.max_daily_loss:
            self.broker.close_all_by_magic(self.inputs.magic_num)
            s.current_state = BotState.STATE_OFF
            s.is_system_on = False
            s.dash_status = "STOP GLOBAL DIÁRIO"
            sm.telemetry.emit(EventType.DAILY_STOP, self.broker.symbol, {"total": total})
            return

        if self.inputs.max_daily_profit > 0 and total >= self.inputs.max_daily_profit:
            self.broker.close_all_by_magic(self.inputs.magic_num)
            s.current_state = BotState.STATE_OFF
            s.is_system_on = False
            s.dash_status = f"META BATIDA ($ {total:.2f})"
            sm.telemetry.emit(EventType.DAILY_TARGET, self.broker.symbol, {"total": total})

    # ---------------- ManageCapitalTrailing() ----------------
    def manage_capital_trailing(self, sm: CycleTheoryStateMachine) -> None:
        s = sm.state
        if not self.inputs.use_capital_trail or s.current_state == BotState.STATE_OFF:
            return

        fechado = self._daily_profit()

        if not s.capital_trail_active and fechado >= self.inputs.capital_goal:
            s.capital_trail_active = True
            sm.telemetry.emit(EventType.CAPITAL_TRAIL_ACTIVE, self.broker.symbol, {"fechado": fechado})

        if s.capital_trail_active and fechado <= self.inputs.capital_protect:
            self.broker.close_all_by_magic(self.inputs.magic_num)
            s.current_state = BotState.STATE_OFF
            s.is_system_on = False
            s.dash_status = f"META PROTEGIDA ($ {fechado:.2f})"
            sm.telemetry.emit(EventType.CAPITAL_PROTECTED, self.broker.symbol, {"fechado": fechado})

    # ---------------- CheckTimeAndClose() ----------------
    def check_time_and_close(self, sm: CycleTheoryStateMachine) -> bool:
        s = sm.state
        now = self.broker.now
        agora = now.hour * 60 + now.minute
        inicio = _time_to_minutes(self.inputs.start_time)
        corte = _time_to_minutes(self.inputs.end_entry_time)
        fechamento = _time_to_minutes(self.inputs.close_all_time)

        if agora >= fechamento:
            self.broker.close_all_by_magic(self.inputs.magic_num)
            if s.current_state != BotState.STATE_OFF:
                s.current_state = BotState.STATE_OFF
            s.dash_status = f"MERCADO FECHADO ({now.strftime('%H:%M')})"
            return False

        if s.is_system_on and s.current_state == BotState.STATE_OFF:
            if inicio <= agora < fechamento:
                sm.reset_cycle()
                return True

        if s.current_state != BotState.STATE_TRADING:
            if agora < inicio or agora >= corte:
                s.dash_status = f"FORA DE HORÁRIO ({now.strftime('%H:%M')})"
                return False

        return True
