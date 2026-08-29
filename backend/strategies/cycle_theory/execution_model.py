"""
CYCLE THEORY V111 — FIDELITY PORT
CycleTheoryExecutionModel — equivalente a CalcLot, ExecutarCompra, ExecutarVenda,
GetSmartBuffer do MQ5 (seções 8 e 18-19 da Source Audit).

QUIRK PRESERVADO: CalcLot recebe dist_sl mas NÃO o utiliza para dimensionar
o lote (ver Source Audit, seção V / OBS-04). NÃO "corrigir".
"""
from __future__ import annotations
import math
from typing import Optional

from .enums import EntryMode, LotMode, BotState
from .broker import MockBroker
from .inputs import CycleTheoryInputs
from .state_machine import CycleTheoryStateMachine
from .persistence import CycleTheoryPersistence
from .telemetry import EventType


def get_smart_buffer(inputs: CycleTheoryInputs) -> int:
    """GetSmartBuffer(): 0 NÃO significa 'sem buffer' — ativa fallback de 50 pts."""
    return inputs.stop_buffer if inputs.stop_buffer > 0 else 50


class CycleTheoryExecutionModel:
    def __init__(self, broker: MockBroker, inputs: CycleTheoryInputs,
                 persistence: CycleTheoryPersistence):
        self.broker = broker
        self.inputs = inputs
        self.persistence = persistence

    def calc_lot(self, dist_sl: float) -> float:  # noqa: ARG002 — dist_sl é ignorado DE PROPÓSITO
        """CalcLot(distSL): distSL é recebido mas NUNCA usado, exatamente como no original."""
        lot = self.inputs.fixed_lot

        if self.inputs.lot_mode == LotMode.LOT_AUTO_BALANCE and self.inputs.balance_step > 0:
            steps = math.floor(self.broker.balance / self.inputs.balance_step)
            if steps < 1:
                steps = 1
            lot = steps * self.inputs.fixed_lot

        step = self.broker.volume_step
        mn, mx = self.broker.volume_min, self.broker.volume_max
        lot = math.floor((lot + 1e-10) / step) * step
        lot = max(mn, min(mx, lot))

        # Verificação de margem — original usa ORDER_TYPE_BUY mesmo para venda (quirk preservado)
        margem_necessaria = self._calc_margin_buy(lot)
        livre = self.broker.margin_free
        if margem_necessaria is not None and livre > 0 and margem_necessaria > livre:
            lot = math.floor((lot * (livre / margem_necessaria)) / step) * step
            lot = max(mn, min(mx, lot))

        return lot

    def _calc_margin_buy(self, lot: float):
        """Equivalent boundary for OrderCalcMargin(ORDER_TYPE_BUY, ...).

        None means the broker margin service is unavailable; this mirrors the
        MQ5 branch where OrderCalcMargin returns false and no scaling occurs.
        """
        return self.broker.order_calc_margin_buy(lot)

    def executar_compra(self, sm: CycleTheoryStateMachine, sl: float, ep: float,
                         dist_sl: float) -> bool:
        """ExecutarCompra() — linha 1365-1393."""
        lot = self.calc_lot(dist_sl)
        stops_level = self.broker.stops_level_pts * self.broker.point
        preco_ref = self.broker.ask if self.inputs.entry_mode == EntryMode.ENTRY_MARKET else ep
        if stops_level > 0 and (preco_ref - sl) < stops_level:
            sl = round(preco_ref - stops_level - self.broker.point, self.broker.digits)

        if self.inputs.entry_mode == EntryMode.ENTRY_MARKET:
            ticket = self.broker.buy(lot, sl, 0.0, self.inputs.magic_num)
        else:
            ticket = self.broker.buy_limit(lot, ep, sl, 0.0, self.inputs.magic_num)

        return self._after_order(sm, ticket, is_buy=True,
                                  fill_price=self.broker.ask if self.inputs.entry_mode == EntryMode.ENTRY_MARKET else ep)

    def executar_venda(self, sm: CycleTheoryStateMachine, sl: float, ep: float,
                        dist_sl: float) -> bool:
        """ExecutarVenda() — linha 1396-1424."""
        lot = self.calc_lot(dist_sl)
        stops_level = self.broker.stops_level_pts * self.broker.point
        preco_ref = self.broker.bid if self.inputs.entry_mode == EntryMode.ENTRY_MARKET else ep
        if stops_level > 0 and (sl - preco_ref) < stops_level:
            sl = round(preco_ref + stops_level + self.broker.point, self.broker.digits)

        if self.inputs.entry_mode == EntryMode.ENTRY_MARKET:
            ticket = self.broker.sell(lot, sl, 0.0, self.inputs.magic_num)
        else:
            ticket = self.broker.sell_limit(lot, ep, sl, 0.0, self.inputs.magic_num)

        return self._after_order(sm, ticket, is_buy=False,
                                  fill_price=self.broker.bid if self.inputs.entry_mode == EntryMode.ENTRY_MARKET else ep)

    def _after_order(self, sm: CycleTheoryStateMachine, ticket: Optional[int],
                      is_buy: bool, fill_price: float) -> bool:
        if ticket is not None:
            sm.state.last_order_time = self.broker.now
            sm.state.current_state = BotState.STATE_TRADING
            self.persistence.save_memory(sm)
            sm.telemetry.emit(EventType.ORDER_SUBMITTED, self.broker.symbol,
                               {"is_buy": is_buy, "price": fill_price,
                                "mode": self.inputs.entry_mode.name})
            return True
        else:
            sm.telemetry.emit(EventType.ORDER_ERROR, self.broker.symbol, {"reason": "trade_failed"})
            sm.reset_cycle("ERRO: falha de execução")
            return False
