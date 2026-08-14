"""
CYCLE THEORY V111 — FIDELITY PORT
CycleTheorySignalEngine — equivalente a Processar_Sinais() e às três
estratégias (Estrategia_Split, Estrategia_ZonaNeutra, Estrategia_Expansao),
linhas 1427-1658 do MQ5.

REGRA: nenhuma fórmula, ordem de checagem ou condição foi alterada.
"""
from __future__ import annotations

from .enums import BotState, EntryMode, TriggerMode
from .broker import MockBroker
from .inputs import CycleTheoryInputs
from .state_machine import CycleTheoryStateMachine
from .execution_model import CycleTheoryExecutionModel, get_smart_buffer
from .telemetry import EventType


class CycleTheorySignalEngine:
    def __init__(self, broker: MockBroker, inputs: CycleTheoryInputs,
                 exec_model: CycleTheoryExecutionModel, timeframe: str = "M5"):
        self.broker = broker
        self.inputs = inputs
        self.exec_model = exec_model
        # ENUM_TIMEFRAMES InpFixedTF == PERIOD_CURRENT -> usa _Period do gráfico.
        # Aqui, timeframe representa esse "_Period do gráfico" quando fixed_tf
        # é PERIOD_CURRENT; caso contrário, usa o timeframe fixo configurado.
        self.chart_period = timeframe
        self.working_tf = (timeframe if inputs.fixed_tf == "PERIOD_CURRENT"
                            else inputs.fixed_tf)

    # ---------------- Processar_Sinais() — despacho por estado ----------------
    def process_signals(self, sm: CycleTheoryStateMachine) -> None:
        wtf = self.working_tf
        s = sm.state

        if s.current_state == BotState.STATE_STARTING:
            s.ref_time_start = self.broker.i_time(wtf, 0)
            s.current_state = BotState.STATE_COUNTING
            s.dash_status = "CONTANDO VELAS..."
            sm.telemetry.emit(EventType.CYCLE_STARTED, self.broker.symbol,
                               {"ref_time_start": s.ref_time_start})
            sm.telemetry.emit(EventType.COUNTING_STARTED, self.broker.symbol, {})
            return

        if s.current_state == BotState.STATE_COUNTING:
            self._build_channel(sm, wtf)
            return

        if s.current_state == BotState.STATE_MONITORING:
            self._monitor(sm, wtf)
            return

    # ---------------- STATE_COUNTING -> construção do canal ----------------
    def _build_channel(self, sm: CycleTheoryStateMachine, wtf: str) -> None:
        s = sm.state
        if self.broker.i_bar_shift(wtf, s.ref_time_start) < 5:
            return

        ch_high = self.broker.i_highest(wtf, 4, 1)
        ch_low = self.broker.i_lowest(wtf, 4, 1)
        h = ch_high - ch_low

        if h < self.broker.point or (
            self.inputs.max_channel_size > 0
            and h / self.broker.point > self.inputs.max_channel_size
        ):
            sm.telemetry.emit(EventType.CHANNEL_INVALID, self.broker.symbol, {"height": h})
            sm.reset_cycle("CANAL INVÁLIDO")
            return

        s.ch_high, s.ch_low = ch_high, ch_low

        if self.inputs.split_channel_points > 0 and h >= self.inputs.split_channel_points * self.broker.point:
            s.is_split_active = True
            s.mid_line50 = (ch_high + ch_low) / 2.0
            s.channel_height = h / 2.0
            s.super_size = s.channel_height
            s.dash_status = "AGUARDANDO ROMPIMENTO (SPLIT)"
            sm.telemetry.emit(EventType.SPLIT_ACTIVATED, self.broker.symbol, {})
        else:
            s.is_split_active = False
            s.channel_height = h
            s.super_size = h
            s.dash_status = ("AGUARDANDO ROMPIMENTO ZN"
                              if self.inputs.trigger_mode == TriggerMode.GATILHO_ZONA_NEUTRA
                              else "AGUARDANDO EXPANSÃO")

        sm.telemetry.emit(EventType.CHANNEL_DEFINED, self.broker.symbol,
                           {"ch_high": ch_high, "ch_low": ch_low, "split": s.is_split_active})
        s.current_state = BotState.STATE_MONITORING

    # ---------------- STATE_MONITORING -> despacha estratégia ----------------
    def _monitor(self, sm: CycleTheoryStateMachine, wtf: str) -> None:
        s = sm.state

        if self.inputs.max_daily_trades > 0 and self.broker.daily_trades_count(self.inputs.magic_num) >= self.inputs.max_daily_trades:
            s.dash_status = "MAX TRADES DIÁRIO"
            return
        if self.inputs.max_daily_loss > 0:
            daily_profit, _, _ = self.broker.period_stats(
                self.broker.now.replace(hour=0, minute=0, second=0, microsecond=0),
                self.inputs.magic_num)
            if daily_profit <= -self.inputs.max_daily_loss:
                s.dash_status = "STOP LOSS DIÁRIO"
                return

        close1 = self.broker.i_close(wtf, 1)
        buff = get_smart_buffer(self.inputs) * self.broker.point
        pb = 0.0
        if self.inputs.entry_mode == EntryMode.ENTRY_PULLBACK_25:
            pb = s.super_size * 0.25
        elif self.inputs.entry_mode == EntryMode.ENTRY_PULLBACK_50:
            pb = s.super_size * 0.50

        if s.is_split_active:
            self._estrategia_split(sm, close1, s.ch_high, s.ch_low, buff, pb)
        elif self.inputs.trigger_mode == TriggerMode.GATILHO_ZONA_NEUTRA:
            self._estrategia_zona_neutra(sm, close1, s.ch_high, s.ch_low, buff, pb)
        else:
            self._estrategia_expansao(sm, close1, s.ch_high, s.ch_low, buff, pb)

    # ---------------- Estrategia_Split ----------------
    def _estrategia_split(self, sm: CycleTheoryStateMachine, close: float,
                           high: float, low: float, buff: float, pb: float) -> None:
        s = sm.state
        if self.broker.spread_pts > self.inputs.max_spread:
            s.dash_status = f"ALERTA: SPREAD ALTO ({self.broker.spread_pts})"
            return

        if close > high:
            s.setup_dir = 1
            s.exp_level = high
            s.g_sl_ref = low
            sl = round(s.g_sl_ref - buff, self.broker.digits)
            ep = round(high - pb, self.broker.digits)
            self.exec_model.executar_compra(sm, sl, ep, abs(self.broker.ask - sl))
        elif close < low:
            s.setup_dir = -1
            s.exp_level = low
            s.g_sl_ref = high
            sl = round(s.g_sl_ref + buff, self.broker.digits)
            ep = round(low + pb, self.broker.digits)
            self.exec_model.executar_venda(sm, sl, ep, abs(self.broker.bid - sl))

    # ---------------- Estrategia_ZonaNeutra (estruturalmente idêntica ao Split — ver Source Audit seção G) ----------------
    def _estrategia_zona_neutra(self, sm: CycleTheoryStateMachine, close: float,
                                 high: float, low: float, buff: float, pb: float) -> None:
        s = sm.state
        if self.broker.spread_pts > self.inputs.max_spread:
            s.dash_status = "ALERTA: SPREAD ALTO"
            return

        if close > high:
            s.setup_dir = 1
            s.exp_level = high
            s.g_sl_ref = low
            sl = round(s.g_sl_ref - buff, self.broker.digits)
            ep = round(high - pb, self.broker.digits)
            self.exec_model.executar_compra(sm, sl, ep, abs(self.broker.ask - sl))
        elif close < low:
            s.setup_dir = -1
            s.exp_level = low
            s.g_sl_ref = high
            sl = round(s.g_sl_ref + buff, self.broker.digits)
            ep = round(low + pb, self.broker.digits)
            self.exec_model.executar_venda(sm, sl, ep, abs(self.broker.bid - sl))

    # ---------------- Estrategia_Expansao ----------------
    def _estrategia_expansao(self, sm: CycleTheoryStateMachine, close: float,
                              high: float, low: float, buff: float, pb: float) -> None:
        s = sm.state

        # Fase 1 — identifica direção inicial (SEM checagem de spread — quirk preservado, OBS-02)
        if s.setup_dir == 0:
            if close > high:
                s.setup_dir = 1
                s.channel_height = high - low
                s.exp_level = high + s.channel_height
                s.super_size = s.exp_level - low
                s.g_sl_ref = low
                s.dash_status = "AGUARDANDO COMPRA (EXP)"
                sm.telemetry.emit(EventType.EXPANSION_WAIT_BUY, self.broker.symbol, {})
            elif close < low:
                s.setup_dir = -1
                s.channel_height = high - low
                s.exp_level = low - s.channel_height
                s.super_size = high - s.exp_level
                s.g_sl_ref = high
                s.dash_status = "AGUARDANDO VENDA (EXP)"
                sm.telemetry.emit(EventType.EXPANSION_WAIT_SELL, self.broker.symbol, {})
            return

        if self.broker.spread_pts > self.inputs.max_spread:
            s.dash_status = "ALERTA: SPREAD ALTO"
            return

        # Fase 2 — confirmação ou inversão
        if s.setup_dir == 1:
            if close > s.exp_level:
                sl = round(s.g_sl_ref - buff, self.broker.digits)
                ep = round(s.exp_level - pb, self.broker.digits)
                sm.telemetry.emit(EventType.EXPANSION_CONFIRMED, self.broker.symbol, {"dir": 1})
                self.exec_model.executar_compra(sm, sl, ep, abs(self.broker.ask - sl))
            elif close < low:
                novo_sl_ref = s.exp_level
                s.setup_dir = -1
                s.exp_level = low - s.channel_height
                s.super_size = high - s.exp_level
                s.g_sl_ref = novo_sl_ref
                s.dash_status = "INVERSÃO → VENDA (EXP)"
                sm.telemetry.emit(EventType.SETUP_REVERSED, self.broker.symbol, {"to": -1})
                sl = round(s.g_sl_ref + buff, self.broker.digits)
                ep = round(low + pb, self.broker.digits)
                self.exec_model.executar_venda(sm, sl, ep, abs(self.broker.bid - sl))
        elif s.setup_dir == -1:
            if close < s.exp_level:
                sl = round(s.g_sl_ref + buff, self.broker.digits)
                ep = round(s.exp_level + pb, self.broker.digits)
                sm.telemetry.emit(EventType.EXPANSION_CONFIRMED, self.broker.symbol, {"dir": -1})
                self.exec_model.executar_venda(sm, sl, ep, abs(self.broker.bid - sl))
            elif close > high:
                novo_sl_ref = s.exp_level
                s.setup_dir = 1
                s.exp_level = high + s.channel_height
                s.super_size = s.exp_level - low
                s.g_sl_ref = novo_sl_ref
                s.dash_status = "INVERSÃO → COMPRA (EXP)"
                sm.telemetry.emit(EventType.SETUP_REVERSED, self.broker.symbol, {"to": 1})
                sl = round(s.g_sl_ref - buff, self.broker.digits)
                ep = round(high - pb, self.broker.digits)
                self.exec_model.executar_compra(sm, sl, ep, abs(self.broker.ask - sl))
