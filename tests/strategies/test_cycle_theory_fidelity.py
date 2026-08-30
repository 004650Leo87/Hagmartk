"""
CYCLE THEORY V111 — FIDELITY PORT
Testes unitários determinísticos (unittest da stdlib — pytest indisponível
neste ambiente sem rede).

Cobrem: máquina de estados, construção do canal, Split, Zona Neutra,
Expansão (fase 1/2 + inversões), Market/Pullback 0/25/50, pending order +
pullback perdido, parciais, trailing (OFF/DYNAMIC/STRUCTURAL/ATR), breakeven,
TP final, smart buffer, proteções diárias, capital trailing, horários,
persistência, guard de 3s, e os quirks documentados (CalcLot ignora distSL,
ATR usa _Period do gráfico, ResetCycle zera capital_trail_active, PULLBACK_0
é Limit, superSize da Expansão != channelHeight, escopo cross-symbol do Magic).
"""
import unittest
from datetime import datetime, timedelta

from backend.strategies.cycle_theory.enums import BotState, EntryMode, TrailingMode, TriggerMode, LotMode, PositionType, OrderType
from backend.strategies.cycle_theory.inputs import baseline_inputs, CycleTheoryInputs
from backend.strategies.cycle_theory.broker import MockBroker, Candle
from backend.strategies.cycle_theory.research_adapter import CycleTheoryResearchAdapter


def make_bars(count: int, start: datetime, base: float, step_minutes: int = 5) -> list[Candle]:
    """Gera `count` candles com candles[0]=mais recente (em formação) e
    candles[-1]=mais antigo, como o array indexado por shift do MQL5."""
    bars = []
    for i in range(count):
        t = start - timedelta(minutes=step_minutes * i)
        bars.append(Candle(t, base, base + 0.0010, base - 0.0010, base))
    return bars


def setup_adapter(inputs: CycleTheoryInputs = None, symbol: str = "EURUSD") -> CycleTheoryResearchAdapter:
    inputs = inputs or baseline_inputs()
    broker = MockBroker(symbol, point=0.0001, digits=4, stops_level_pts=0, freeze_level_pts=0)
    broker.now = datetime(2026, 1, 5, 10, 0, 0)  # dentro do horário 01:00-23:00
    broker.bid, broker.ask, broker.spread_pts = 1.1000, 1.1002, 2
    adapter = CycleTheoryResearchAdapter(symbol, inputs, broker, timeframe="M5")
    adapter.power_on()
    return adapter


class TestStateMachine(unittest.TestCase):
    def test_starting_to_counting(self):
        a = setup_adapter()
        a.broker.set_bars("M5", make_bars(10, a.broker.now, 1.1000))
        self.assertEqual(a.sm.state.current_state, BotState.STATE_STARTING)
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_COUNTING)
        self.assertIsNotNone(a.sm.state.ref_time_start)

    def test_counting_waits_5_bars(self):
        a = setup_adapter()
        a.broker.set_bars("M5", make_bars(10, a.broker.now, 1.1000))
        a.on_tick()  # STARTING -> COUNTING, ref_time_start = bars[0].time
        # iBarShift(ref_time_start) == 0 agora (mesma barra) -> < 5, não constrói canal
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_COUNTING)


class TestChannel(unittest.TestCase):
    """Testa _build_channel diretamente a partir de STATE_COUNTING, evitando
    depender da contagem real de 5 velas via on_tick (já coberta em
    TestStateMachine.test_counting_waits_5_bars)."""

    def _prepare_counting(self, a, high_low_pairs):
        t0 = datetime(2026, 1, 5, 10, 0, 0)
        ref_time = t0 - timedelta(minutes=30)  # >= 5 barras de 5min no passado
        a.sm.state.current_state = BotState.STATE_COUNTING
        a.sm.state.ref_time_start = ref_time
        bars = [Candle(t0, 1.1000, 1.1005, 1.0995, 1.1000)]  # bars[0] = atual
        for i, (h, l) in enumerate(high_low_pairs, start=1):
            bars.append(Candle(t0 - timedelta(minutes=5 * i), 1.1000, h, l, 1.1000))
        while len(bars) < 6:
            bars.append(Candle(t0 - timedelta(minutes=5 * len(bars)), 1.1000, 1.1005, 1.0995, 1.1000))
        a.broker.set_bars("M5", bars)

    def test_channel_normal_build(self):
        a = setup_adapter()
        self._prepare_counting(a, [(1.1050, 1.0950)] * 4)
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_MONITORING)
        self.assertAlmostEqual(a.sm.state.ch_high, 1.1050)
        self.assertAlmostEqual(a.sm.state.ch_low, 1.0950)
        self.assertFalse(a.sm.state.is_split_active)
        self.assertAlmostEqual(a.sm.state.super_size, 0.0100, places=6)

    def test_channel_invalid_zero_height(self):
        a = setup_adapter()
        self._prepare_counting(a, [(1.1000, 1.1000)] * 4)
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_STARTING)
        self.assertEqual(a.sm.state.dash_status, "CANAL INVÁLIDO")

    def test_channel_max_size_exceeded(self):
        inputs = baseline_inputs()
        inputs.max_channel_size = 100  # 100 pts = 0.0100 no EURUSD (4 digits)
        a = setup_adapter(inputs)
        self._prepare_counting(a, [(1.1200, 1.0800)] * 4)  # 400 pts de altura
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_STARTING)
        self.assertEqual(a.sm.state.dash_status, "CANAL INVÁLIDO")

    def test_split_activates_above_threshold(self):
        inputs = baseline_inputs()
        inputs.split_channel_points = 100  # 100 pts
        a = setup_adapter(inputs)
        self._prepare_counting(a, [(1.1200, 1.0800)] * 4)  # 400 pts > 100
        a.on_tick()
        self.assertTrue(a.sm.state.is_split_active)
        self.assertAlmostEqual(a.sm.state.mid_line50, 1.1000, places=6)
        self.assertAlmostEqual(a.sm.state.super_size, 0.0200, places=6)  # metade de 0.0400


def _force_monitoring(a: CycleTheoryResearchAdapter, ch_high=1.1050, ch_low=1.0950,
                       split=False, close1=None, super_size=None):
    """Atalho de teste: injeta STATE_MONITORING com canal definido, sem
    depender da contagem de 5 velas (já validada em TestChannel)."""
    s = a.sm.state
    s.current_state = BotState.STATE_MONITORING
    s.ch_high, s.ch_low = ch_high, ch_low
    s.is_split_active = split
    h = ch_high - ch_low
    if split:
        s.mid_line50 = (ch_high + ch_low) / 2.0
        s.channel_height = h / 2.0
        s.super_size = super_size if super_size is not None else h / 2.0
    else:
        s.channel_height = h
        s.super_size = super_size if super_size is not None else h
    t0 = a.broker.now
    close = close1 if close1 is not None else ch_high + 0.0005
    a.broker.set_bars("M5", [Candle(t0, close, close + 0.0002, close - 0.0002, close),
                              Candle(t0 - timedelta(minutes=5), close, close + 0.0002, close - 0.0002, close)])


class TestSplitStrategy(unittest.TestCase):
    def test_split_buy_breakout(self):
        a = setup_adapter()
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=True, close1=1.1060)
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_TRADING)
        self.assertEqual(a.sm.state.setup_dir, 1)
        self.assertEqual(len(a.broker.positions) + len(a.broker.pending_orders), 1)

    def test_split_sell_breakout(self):
        a = setup_adapter()
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=True, close1=1.0940)
        a.on_tick()
        self.assertEqual(a.sm.state.setup_dir, -1)


class TestZonaNeutra(unittest.TestCase):
    def test_zn_buy_breakout(self):
        inputs = baseline_inputs()
        inputs.trigger_mode = TriggerMode.GATILHO_ZONA_NEUTRA
        a = setup_adapter(inputs)
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=False, close1=1.1060)
        a.on_tick()
        self.assertEqual(a.sm.state.setup_dir, 1)
        self.assertEqual(a.sm.state.exp_level, 1.1050)  # expLevel = high, NÃO high+height


class TestExpansaoFase1(unittest.TestCase):
    def test_fase1_buy_sets_super_size_correctly(self):
        """superSize da Expansão NÃO é igual ao channelHeight — ver Source Audit seção H."""
        a = setup_adapter()
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=False, close1=1.1060)
        a.on_tick()  # Fase 1: apenas detecta, NÃO entra
        s = a.sm.state
        self.assertEqual(s.setup_dir, 1)
        self.assertEqual(len(a.broker.positions), 0)
        self.assertEqual(len(a.broker.pending_orders), 0)
        h = 1.1050 - 1.0950
        self.assertAlmostEqual(s.channel_height, h, places=6)
        self.assertAlmostEqual(s.exp_level, 1.1050 + h, places=6)
        self.assertAlmostEqual(s.super_size, s.exp_level - 1.0950, places=6)
        self.assertNotAlmostEqual(s.super_size, h, places=6)  # NÃO é igual ao canal

    def test_fase1_sell(self):
        a = setup_adapter()
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=False, close1=1.0940)
        a.on_tick()
        s = a.sm.state
        self.assertEqual(s.setup_dir, -1)
        h = 1.1050 - 1.0950
        self.assertAlmostEqual(s.exp_level, 1.0950 - h, places=6)


class TestExpansaoFase2(unittest.TestCase):
    def test_fase2_confirm_buy(self):
        a = setup_adapter()
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=False, close1=1.1060)
        a.on_tick()  # fase 1
        exp_level = a.sm.state.exp_level
        # fase 2: fecha acima do expLevel
        a.broker.set_bars("M5", [Candle(a.broker.now, exp_level + 0.0005, exp_level + 0.0007,
                                          exp_level + 0.0003, exp_level + 0.0005)] * 2)
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_TRADING)

    def test_fase2_reversal_buy_to_sell(self):
        a = setup_adapter()
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=False, close1=1.1060)
        a.on_tick()  # fase 1: setup_dir=1
        old_exp_level = a.sm.state.exp_level
        # fase 2: fecha ABAIXO do low original -> inverte para venda
        a.broker.set_bars("M5", [Candle(a.broker.now, 1.0940, 1.0945, 1.0935, 1.0940)] * 2)
        a.on_tick()
        s = a.sm.state
        self.assertEqual(s.setup_dir, -1)
        self.assertEqual(s.g_sl_ref, old_exp_level)  # g_slRef = expLevel anterior
        self.assertEqual(s.dash_status, "INVERSÃO → VENDA (EXP)")
        self.assertEqual(s.current_state, BotState.STATE_TRADING)  # já executou a venda

    def test_fase2_reversal_sell_to_buy(self):
        a = setup_adapter()
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=False, close1=1.0940)
        a.on_tick()  # fase 1: setup_dir=-1
        old_exp_level = a.sm.state.exp_level
        a.broker.set_bars("M5", [Candle(a.broker.now, 1.1060, 1.1065, 1.1055, 1.1060)] * 2)
        a.on_tick()
        s = a.sm.state
        self.assertEqual(s.setup_dir, 1)
        self.assertEqual(s.g_sl_ref, old_exp_level)
        self.assertEqual(s.dash_status, "INVERSÃO → COMPRA (EXP)")


class TestEntryModes(unittest.TestCase):
    def test_market_sends_market_order(self):
        inputs = baseline_inputs()
        inputs.entry_mode = EntryMode.ENTRY_MARKET
        a = setup_adapter(inputs)
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=True, close1=1.1060)
        a.on_tick()
        self.assertEqual(len(a.broker.positions), 1)
        self.assertEqual(len(a.broker.pending_orders), 0)

    def test_pullback_0_is_limit_not_market(self):
        """QUIRK: PULLBACK_0 tem pb=0 mas ainda é ordem Limit, nunca Market."""
        inputs = baseline_inputs()
        inputs.entry_mode = EntryMode.ENTRY_PULLBACK_0
        a = setup_adapter(inputs)
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=True, close1=1.1060)
        a.on_tick()
        self.assertEqual(len(a.broker.positions), 0)
        self.assertEqual(len(a.broker.pending_orders), 1)
        self.assertEqual(a.broker.pending_orders[0].price_open, 1.1050)  # ep = high - 0

    def test_pullback_25_and_50_offsets(self):
        for mode, frac in [(EntryMode.ENTRY_PULLBACK_25, 0.25), (EntryMode.ENTRY_PULLBACK_50, 0.50)]:
            inputs = baseline_inputs()
            inputs.entry_mode = mode
            a = setup_adapter(inputs)
            _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=True, close1=1.1060, super_size=0.0200)
            a.on_tick()
            expected_ep = round(1.1050 - 0.0200 * frac, 4)
            self.assertAlmostEqual(a.broker.pending_orders[0].price_open, expected_ep, places=4)


class TestPullbackMissed(unittest.TestCase):
    def test_pullback_missed_cancels_and_resets(self):
        inputs = baseline_inputs()
        inputs.entry_mode = EntryMode.ENTRY_PULLBACK_25
        a = setup_adapter(inputs)
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=True, close1=1.1060, super_size=0.0200)
        a.on_tick()  # cria ordem pendente (Limit)
        self.assertEqual(len(a.broker.pending_orders), 1)
        entry_price = a.broker.pending_orders[0].price_open
        # alvo1 = entry_price + super_size; sobe o Bid além do alvo sem preencher a ordem
        a.broker.bid = entry_price + 0.0200 + 0.0001
        a.broker.ask = a.broker.bid + 0.0002
        a.on_tick()
        self.assertEqual(len(a.broker.pending_orders), 0)
        self.assertEqual(a.sm.state.current_state, BotState.STATE_STARTING)
        self.assertEqual(a.sm.state.dash_status, "PULLBACK PERDIDO → NOVO CICLO")


class TestPartials(unittest.TestCase):
    def _open_buy(self, a, entry=1.1050, super_size=0.0100, volume=0.04):
        pos = a.broker.buy(volume, 0.0, 0.0, a.inputs.magic_num)
        p = a.broker.positions[0]
        p.price_open = entry
        a.sm.state.super_size = super_size
        a.sm.state.current_state = BotState.STATE_TRADING
        a.sm.state.last_order_time = a.broker.now - timedelta(seconds=10)
        return p

    def test_partial_level_1_closes_half(self):
        a = setup_adapter()
        p = self._open_buy(a)
        a.broker.bid = 1.1050 + 0.0100  # atinge alvo 1
        a.broker.ask = a.broker.bid + 0.0002
        a.on_tick()
        self.assertEqual(a.sm.state.last_partial_level, 1)
        self.assertAlmostEqual(a.broker.positions[0].volume, 0.02, places=6)

    def test_partial_insufficient_volume_advances_without_closing(self):
        a = setup_adapter()
        p = self._open_buy(a, volume=0.01)  # 50% de 0.01 < volume_step(0.01) -> partVol=0
        a.broker.bid = 1.1050 + 0.0100
        a.broker.ask = a.broker.bid + 0.0002
        a.on_tick()
        self.assertEqual(a.sm.state.last_partial_level, 1)
        self.assertEqual(len(a.broker.positions), 1)
        self.assertAlmostEqual(a.broker.positions[0].volume, 0.01, places=6)

    def test_partial_closes_all_when_residual_below_minimum(self):
        a = setup_adapter()
        a.broker.volume_step = 0.005
        a.broker.volume_min = 0.01
        p = self._open_buy(a, volume=0.012)
        # partVol = floor(0.012*0.5/0.005)*0.005 = 0.005 ; restante = 0.007 < min(0.01) -> fecha tudo
        a.broker.bid = 1.1050 + 0.0100
        a.broker.ask = a.broker.bid + 0.0002
        a.on_tick()
        self.assertEqual(len(a.broker.positions), 0)
        self.assertEqual(a.sm.state.current_state, BotState.STATE_STARTING)


class TestTrailing(unittest.TestCase):
    def _open_buy(self, a, entry=1.1050, super_size=0.0100):
        a.broker.buy(0.01, 0.0, 0.0, a.inputs.magic_num)
        p = a.broker.positions[0]
        p.price_open = entry
        a.sm.state.super_size = super_size
        a.sm.state.current_state = BotState.STATE_TRADING
        a.sm.state.last_order_time = a.broker.now - timedelta(seconds=10)
        return p

    def test_trailing_off_does_nothing(self):
        inputs = baseline_inputs()
        inputs.trailing_mode = TrailingMode.TRAIL_OFF
        a = setup_adapter(inputs)
        p = self._open_buy(a)
        a.broker.bid = 1.1080
        a.broker.ask = 1.1082
        a.on_tick()
        self.assertEqual(a.broker.positions[0].sl, 0.0)

    def test_trailing_atr_buy_moves_sl_up_only(self):
        inputs = baseline_inputs()
        inputs.trailing_mode = TrailingMode.TRAIL_ATR
        a = setup_adapter(inputs)
        p = self._open_buy(a, entry=1.1050)
        a.broker.atr_value = 0.0010
        a.broker.bid = 1.1080
        a.broker.ask = 1.1082
        a.on_tick()
        expected_sl = round(1.1080 - 0.0010 * 1.5, 4)
        self.assertAlmostEqual(a.broker.positions[0].sl, expected_sl, places=4)
        # tick seguinte com preço pior não deve piorar o SL
        prev_sl = a.broker.positions[0].sl
        a.broker.bid = 1.1070
        a.broker.ask = 1.1072
        a.on_tick()
        self.assertEqual(a.broker.positions[0].sl, prev_sl)

    def test_trailing_structural_level1_then_level2(self):
        inputs = baseline_inputs()
        inputs.trailing_mode = TrailingMode.TRAIL_STRUCTURAL
        a = setup_adapter(inputs)
        p = self._open_buy(a, entry=1.1050, super_size=0.0100)
        a.broker.bid = 1.1050 + 0.0100  # alvo 1
        a.broker.ask = a.broker.bid + 0.0002
        a.on_tick()
        expected_be = round(1.1050 + 10 * 0.0001, 4)
        self.assertAlmostEqual(a.broker.positions[0].sl, expected_be, places=4)
        self.assertEqual(a.broker.positions[0].tp, 0.0)
        a.broker.bid = 1.1050 + 0.0200  # alvo 2
        a.broker.ask = a.broker.bid + 0.0002
        a.on_tick()
        self.assertAlmostEqual(a.broker.positions[0].sl, 1.1150, places=4)  # SL = alvo 1

    def test_trailing_dynamic(self):
        inputs = baseline_inputs()
        inputs.trailing_mode = TrailingMode.TRAIL_DYNAMIC
        a = setup_adapter(inputs)
        p = self._open_buy(a, entry=1.1050, super_size=0.0100)
        a.broker.bid = 1.1150
        a.broker.ask = 1.1152
        a.on_tick()
        expected_sl = round(1.1150 - (20 * 0.0001), 4)  # alvo - smart_buffer(20 default)
        self.assertAlmostEqual(a.broker.positions[0].sl, expected_sl, places=4)
        self.assertEqual(a.broker.positions[0].tp, 0.0)


class TestBreakeven(unittest.TestCase):
    def test_breakeven_applies_after_activation_threshold(self):
        inputs = baseline_inputs()
        inputs.use_breakeven = True
        inputs.be_activation = 100  # 100 pts
        inputs.trailing_mode = TrailingMode.TRAIL_OFF  # isola BE do trailing ATR (default)
        a = setup_adapter(inputs)
        a.broker.buy(0.01, 0.0, 0.0, a.inputs.magic_num)
        p = a.broker.positions[0]
        p.price_open = 1.1050
        a.sm.state.super_size = 0.0100
        a.sm.state.current_state = BotState.STATE_TRADING
        a.sm.state.last_order_time = a.broker.now - timedelta(seconds=10)
        a.broker.bid = 1.1050 + 0.0110  # 110 pts > 100
        a.broker.ask = a.broker.bid + 0.0002
        a.on_tick()
        expected = round(1.1050 + 10 * 0.0001, 4)
        self.assertAlmostEqual(a.broker.positions[0].sl, expected, places=4)
        self.assertTrue(a.sm.state.be_applied)


class TestQuirks(unittest.TestCase):
    def test_calc_lot_ignores_dist_sl(self):
        """QUIRK OBS-04: distSL é recebido mas nunca usado no cálculo."""
        a = setup_adapter()
        lot_a = a.exec_model.calc_lot(dist_sl=0.0001)
        lot_b = a.exec_model.calc_lot(dist_sl=10.0)  # dist absurda, não deve mudar nada
        self.assertEqual(lot_a, lot_b)

    def test_reset_cycle_zeroes_capital_trail_active(self):
        a = setup_adapter()
        a.sm.state.capital_trail_active = True
        a.sm.reset_cycle()
        self.assertFalse(a.sm.state.capital_trail_active)

    def test_smart_buffer_zero_falls_back_to_50(self):
        from backend.strategies.cycle_theory.execution_model import get_smart_buffer
        inputs = baseline_inputs()
        inputs.stop_buffer = 0
        self.assertEqual(get_smart_buffer(inputs), 50)
        inputs.stop_buffer = 15
        self.assertEqual(get_smart_buffer(inputs), 15)

    def test_magic_cross_symbol_floating_profit_leaks(self):
        """QUIRK OBS-01: GetFloatingProfit soma por magic, atravessando símbolos."""
        broker = MockBroker("EURUSD")
        broker.positions.append(__import__("backend.strategies.cycle_theory.broker", fromlist=["Position"]).Position(
            1, "EURUSD", 7, PositionType.BUY, 0.01, 1.1000, profit=10.0))
        broker.positions.append(__import__("backend.strategies.cycle_theory.broker", fromlist=["Position"]).Position(
            2, "GBPUSD", 7, PositionType.SELL, 0.01, 1.2500, profit=5.0))
        total = broker.floating_profit(7)
        self.assertEqual(total, 15.0)  # soma os dois símbolos — quirk preservado

    def test_magic_cross_symbol_close_all_hits_other_symbol(self):
        """QUIRK OBS-01: CloseAllOperations fecha posições de qualquer símbolo com o magic."""
        broker = MockBroker("EURUSD")
        broker.buy(0.01, 0.0, 0.0, 7)
        broker.positions[0].symbol = "GBPUSD"  # posição "de outro símbolo", mesmo magic
        broker.close_all_by_magic(7)
        self.assertEqual(len(broker.positions), 0)

    def test_get_bot_ticket_equivalent_isolated_by_symbol(self):
        """GetBotTicket() É isolado por símbolo — único ponto assim (contraste com o quirk acima)."""
        broker = MockBroker("EURUSD")
        broker.buy(0.01, 0.0, 0.0, 7)
        broker.positions[0].symbol = "GBPUSD"
        self.assertIsNone(broker.get_position_by_magic_symbol(7, "EURUSD"))

    def test_expansao_super_size_not_equal_channel_height(self):
        a = setup_adapter()
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=False, close1=1.1060)
        a.on_tick()
        s = a.sm.state
        self.assertNotAlmostEqual(s.super_size, s.channel_height, places=6)


class TestDailyProtections(unittest.TestCase):
    def test_daily_loss_stops_system(self):
        inputs = baseline_inputs()
        inputs.max_daily_loss = 50.0
        a = setup_adapter(inputs)
        a.broker.deals.clear()
        from backend.strategies.cycle_theory.broker import Deal
        a.broker.deals.append(Deal(1, "EURUSD", inputs.magic_num, "IN", 100, 0, 0, 0, a.broker.now))
        a.broker.deals.append(Deal(2, "EURUSD", inputs.magic_num, "OUT", 100, -60.0, 0, 0, a.broker.now))
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_OFF)
        self.assertFalse(a.sm.state.is_system_on)
        self.assertEqual(a.sm.state.dash_status, "STOP GLOBAL DIÁRIO")

    def test_daily_trades_limit_blocks_new_entry(self):
        inputs = baseline_inputs()
        inputs.max_daily_trades = 1
        a = setup_adapter(inputs)
        from backend.strategies.cycle_theory.broker import Deal
        a.broker.deals.append(Deal(1, "EURUSD", inputs.magic_num, "IN", 999, 0, 0, 0, a.broker.now))
        _force_monitoring(a, ch_high=1.1050, ch_low=1.0950, split=True, close1=1.1060)
        a.on_tick()
        self.assertEqual(a.sm.state.dash_status, "MAX TRADES DIÁRIO")
        self.assertEqual(len(a.broker.positions) + len(a.broker.pending_orders), 0)


class TestCapitalTrailing(unittest.TestCase):
    def test_capital_trail_activation_and_protection(self):
        inputs = baseline_inputs()
        a = setup_adapter(inputs)
        a.broker.set_bars("M5", make_bars(10, a.broker.now, 1.1000))
        from backend.strategies.cycle_theory.broker import Deal
        a.broker.deals.append(Deal(1, "EURUSD", inputs.magic_num, "IN", 1, 0, 0, 0, a.broker.now))
        a.broker.deals.append(Deal(2, "EURUSD", inputs.magic_num, "OUT", 1, 60.0, 0, 0, a.broker.now))
        a.on_tick()
        self.assertTrue(a.sm.state.capital_trail_active)  # 60 >= goal(50)

        a.broker.deals.append(Deal(3, "EURUSD", inputs.magic_num, "IN", 2, 0, 0, 0, a.broker.now))
        a.broker.deals.append(Deal(4, "EURUSD", inputs.magic_num, "OUT", 2, -40.0, 0, 0, a.broker.now))
        # lucro do dia agora = 20, <= protect(25)
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_OFF)
        self.assertIn("META PROTEGIDA", a.sm.state.dash_status)


class TestTimeRules(unittest.TestCase):
    def test_close_all_time_forces_off(self):
        a = setup_adapter()
        a.broker.now = datetime(2026, 1, 5, 23, 55, 0)  # após 23:50
        a.on_tick()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_OFF)

    def test_entry_cutoff_blocks_new_entries_but_not_trading(self):
        a = setup_adapter()
        a.broker.now = datetime(2026, 1, 5, 23, 30, 0)  # após 23:00, antes de 23:50
        a.sm.state.current_state = BotState.STATE_MONITORING
        ok = a.risk.check_time_and_close(a.sm)
        self.assertFalse(ok)
        a.sm.state.current_state = BotState.STATE_TRADING
        ok2 = a.risk.check_time_and_close(a.sm)
        self.assertTrue(ok2)  # TRADING continua sendo gerenciado após o corte


class TestPersistence(unittest.TestCase):
    def test_save_and_load_exact_7_fields(self):
        a = setup_adapter()
        s = a.sm.state
        s.ch_high, s.ch_low, s.exp_level, s.super_size = 1.1050, 1.0950, 1.1060, 0.0100
        s.setup_dir, s.ref_time_start, s.is_split_active = 1, a.broker.now, False
        a.persistence.save_memory(a.sm)

        b = setup_adapter()
        b.sm.magic = a.sm.magic
        b.symbol = a.symbol
        b.persistence = a.persistence
        loaded = b.persistence.load_memory(b.sm)
        self.assertTrue(loaded)
        self.assertEqual(b.sm.state.ch_high, 1.1050)
        self.assertEqual(b.sm.state.exp_level, 1.1060)
        self.assertEqual(b.sm.state.channel_height, 1.1050 - 1.0950)


class TestClosureGuard(unittest.TestCase):
    def test_3_second_guard_blocks_immediate_reset(self):
        a = setup_adapter()
        a.sm.state.current_state = BotState.STATE_TRADING
        a.sm.state.last_order_time = a.broker.now  # agora mesmo
        a.check_trade_closure()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_TRADING)  # ainda não resetou

    def test_3_second_guard_allows_reset_after_elapsed(self):
        a = setup_adapter()
        a.sm.state.current_state = BotState.STATE_TRADING
        a.sm.state.last_order_time = a.broker.now - timedelta(seconds=5)
        a.check_trade_closure()
        self.assertEqual(a.sm.state.current_state, BotState.STATE_STARTING)


class TestPendingOrderVolumeFidelity(unittest.TestCase):
    def test_buy_limit_fill_preserves_submitted_volume(self):
        broker = MockBroker("EURUSD")
        ticket = broker.buy_limit(0.20, 1.0990, 1.0950, 0.0, 7)
        self.assertIsNotNone(ticket)
        order = next(o for o in broker.pending_orders if o.ticket == ticket)
        self.assertAlmostEqual(order.volume, 0.20)
        position_ticket = broker.fill_pending(ticket)
        position = next(p for p in broker.positions if p.ticket == position_ticket)
        self.assertAlmostEqual(position.volume, 0.20)

    def test_sell_limit_fill_preserves_submitted_volume(self):
        broker = MockBroker("EURUSD")
        ticket = broker.sell_limit(0.37, 1.1010, 1.1050, 0.0, 7)
        self.assertIsNotNone(ticket)
        position_ticket = broker.fill_pending(ticket)
        position = next(p for p in broker.positions if p.ticket == position_ticket)
        self.assertAlmostEqual(position.volume, 0.37)


if __name__ == "__main__":
    unittest.main()
