"""
CYCLE THEORY V111 — FIDELITY PORT
CycleTheoryPositionManager — equivalente a ManagePartials(), ManageTrailing(),
SyncTargetAndVisuals(), PodeModificar() (linhas 412-441, 1051-1264 do MQ5).
"""
from __future__ import annotations
import math

from .enums import TrailingMode, PositionType
from .broker import MockBroker, Position
from .inputs import CycleTheoryInputs, BE_PROTECT_PTS
from .state_machine import CycleTheoryStateMachine
from .persistence import CycleTheoryPersistence
from .execution_model import get_smart_buffer
from .telemetry import EventType


def pode_modificar(broker: MockBroker, tipo: PositionType, novo_sl: float, novo_tp: float) -> bool:
    """PodeModificar() — linha 412-441."""
    freeze = broker.freeze_level_pts * broker.point
    stops = broker.stops_level_pts * broker.point
    min_dist = max(freeze, stops)
    if min_dist <= 0:
        return True

    bid, ask = broker.bid, broker.ask
    if tipo == PositionType.BUY:
        if novo_sl > 0 and (bid - novo_sl) < min_dist:
            return False
        if novo_tp > 0 and (novo_tp - bid) < min_dist:
            return False
    else:
        if novo_sl > 0 and (novo_sl - ask) < min_dist:
            return False
        if novo_tp > 0 and (ask - novo_tp) < min_dist:
            return False
    return True


class CycleTheoryPositionManager:
    def __init__(self, broker: MockBroker, inputs: CycleTheoryInputs,
                 persistence: CycleTheoryPersistence):
        self.broker = broker
        self.inputs = inputs
        self.persistence = persistence

    # ---------------- ManagePartials() ----------------
    def manage_partials(self, sm: CycleTheoryStateMachine) -> bool:
        """Retorna True se a posição foi fechada por completo (equivalente ao
        `return true` do original, que interrompe o ciclo ManagePartials->Trailing)."""
        if not self.inputs.use_partial or self.inputs.partial_pct <= 0:
            return False

        pos = self.broker.get_position_by_magic_symbol(self.inputs.magic_num, self.broker.symbol)
        if pos is None:
            return False

        s = sm.state
        # vol lido UMA VEZ antes do loop — quirk preservado (Source Audit seção P)
        vol = pos.volume
        preco = self.broker.bid if pos.type == PositionType.BUY else self.broker.ask

        for i in range(1, self.inputs.expansion_levels + 1):
            if s.last_partial_level >= i:
                continue

            alvo = (pos.price_open + s.super_size * i if pos.type == PositionType.BUY
                    else pos.price_open - s.super_size * i)
            atingiu = ((pos.type == PositionType.BUY and preco >= alvo) or
                       (pos.type == PositionType.SELL and preco <= alvo))
            if not atingiu:
                continue

            step = self.broker.volume_step
            min_vol = self.broker.volume_min
            part_vol = math.floor(vol * (self.inputs.partial_pct / 100.0) / step) * step
            restante = round(vol - part_vol, 8)

            if restante < min_vol:
                if self.broker.position_close(pos.ticket):
                    sm.telemetry.emit(EventType.POSITION_CLOSED, self.broker.symbol,
                                       {"reason": f"partial_100_level_{i}"})
                    sm.reset_cycle()
                    return True
            elif part_vol >= min_vol:
                if self.broker.position_close_partial(pos.ticket, part_vol):
                    s.last_partial_level = i
                    s.partial_status = f"NÍVEL {i}"
                    sm.telemetry.emit(EventType.PARTIAL_EXECUTED, self.broker.symbol,
                                       {"level": i, "volume": part_vol})
            else:
                # volume insuficiente — avança nível sem fechar (quirk preservado)
                s.last_partial_level = i

        return False

    # ---------------- SyncTargetAndVisuals() (TP final) ----------------
    def sync_target_and_visuals(self, sm: CycleTheoryStateMachine, pos: Position) -> None:
        s = sm.state
        if s.super_size <= self.broker.point:
            return
        buf = get_smart_buffer(self.inputs) * self.broker.point
        correct_tp = (pos.price_open + (s.super_size * self.inputs.expansion_levels) - buf
                      if pos.type == PositionType.BUY
                      else pos.price_open - (s.super_size * self.inputs.expansion_levels) + buf)
        correct_tp = round(correct_tp, self.broker.digits)
        current_tp = round(pos.tp, self.broker.digits)
        if abs(correct_tp - current_tp) > self.broker.point and pode_modificar(
                self.broker, pos.type, pos.sl, correct_tp):
            self.broker.position_modify(pos.ticket, pos.sl, correct_tp)

    # ---------------- ManageTrailing() ----------------
    def manage_trailing(self, sm: CycleTheoryStateMachine) -> None:
        pos = self.broker.get_position_by_magic_symbol(self.inputs.magic_num, self.broker.symbol)
        if pos is None:
            return

        s = sm.state
        preco = self.broker.bid if pos.type == PositionType.BUY else self.broker.ask
        abertura = pos.price_open

        if s.super_size <= self.broker.point:
            self.persistence.load_memory(sm)

        self.sync_target_and_visuals(sm, pos)
        if s.dash_status != "EM OPERAÇÃO":
            s.dash_status = "EM OPERAÇÃO"

        # Breakeven — roda ANTES do bloco TRAIL_OFF (mesmo com trailing desligado)
        if self.inputs.use_breakeven and not s.be_applied:
            pts = ((preco - abertura) / self.broker.point if pos.type == PositionType.BUY
                   else (abertura - preco) / self.broker.point)
            if pts >= self.inputs.be_activation:
                be_price = round(
                    abertura + (BE_PROTECT_PTS * self.broker.point) if pos.type == PositionType.BUY
                    else abertura - (BE_PROTECT_PTS * self.broker.point),
                    self.broker.digits)
                if pode_modificar(self.broker, pos.type, be_price, pos.tp) and \
                        self.broker.position_modify(pos.ticket, be_price, pos.tp):
                    s.be_applied = True
                    sm.telemetry.emit(EventType.BREAKEVEN_APPLIED, self.broker.symbol, {})

        if self.inputs.trailing_mode == TrailingMode.TRAIL_OFF:
            return

        if self.inputs.trailing_mode == TrailingMode.TRAIL_ATR:
            atr = self.broker.atr_value
            dist = atr * self.inputs.atr_multiplier
            if pos.type == PositionType.BUY:
                novo_sl = round(preco - dist, self.broker.digits)
                if novo_sl > pos.sl and novo_sl > abertura and pode_modificar(self.broker, pos.type, novo_sl, pos.tp):
                    self.broker.position_modify(pos.ticket, novo_sl, pos.tp)
                    sm.telemetry.emit(EventType.TRAILING_UPDATED, self.broker.symbol, {"sl": novo_sl})
            else:
                novo_sl = round(preco + dist, self.broker.digits)
                if (pos.sl == 0 or novo_sl < pos.sl) and novo_sl < abertura and pode_modificar(self.broker, pos.type, novo_sl, pos.tp):
                    self.broker.position_modify(pos.ticket, novo_sl, pos.tp)
                    sm.telemetry.emit(EventType.TRAILING_UPDATED, self.broker.symbol, {"sl": novo_sl})
            return

        # TRAIL_DYNAMIC / TRAIL_STRUCTURAL — por nível de alvo, com break no primeiro elegível
        trail_buf = get_smart_buffer(self.inputs) * self.broker.point
        for i in range(1, self.inputs.expansion_levels + 1):
            if s.tr_current_level >= i:
                continue

            alvo = (abertura + s.super_size * i if pos.type == PositionType.BUY
                    else abertura - s.super_size * i)
            atingiu = ((pos.type == PositionType.BUY and self.broker.bid >= alvo) or
                       (pos.type == PositionType.SELL and self.broker.ask <= alvo))
            if not atingiu:
                continue

            sm.telemetry.emit(EventType.TARGET_LEVEL_REACHED, self.broker.symbol, {"level": i})

            novo_sl = 0.0
            if self.inputs.trailing_mode == TrailingMode.TRAIL_DYNAMIC:
                novo_sl = round(alvo - trail_buf if pos.type == PositionType.BUY else alvo + trail_buf,
                                 self.broker.digits)
            elif self.inputs.trailing_mode == TrailingMode.TRAIL_STRUCTURAL:
                if i == 1:
                    novo_sl = round(
                        abertura + (BE_PROTECT_PTS * self.broker.point) if pos.type == PositionType.BUY
                        else abertura - (BE_PROTECT_PTS * self.broker.point),
                        self.broker.digits)
                else:
                    alvo_anterior = (abertura + s.super_size * (i - 1) if pos.type == PositionType.BUY
                                      else abertura - s.super_size * (i - 1))
                    novo_sl = round(alvo_anterior, self.broker.digits)

            seguro = ((pos.type == PositionType.BUY and novo_sl > pos.sl) or
                      (pos.type == PositionType.SELL and (pos.sl == 0 or novo_sl < pos.sl)))

            if seguro and pode_modificar(self.broker, pos.type, novo_sl, 0.0) and \
                    self.broker.position_modify(pos.ticket, novo_sl, 0.0):
                s.tr_current_level = i
                sm.telemetry.emit(EventType.TRAILING_UPDATED, self.broker.symbol, {"sl": novo_sl, "level": i})
                break
