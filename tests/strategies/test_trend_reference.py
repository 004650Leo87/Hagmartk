from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from backend.backtest.engine import BacktestEngine
from backend.backtest.simulator import CostsConfig, IntrabarPolicy, simulate_trade_outcome
from backend.domain.events import Direction
from backend.indicators.atr import ATRIndicator
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy


def create_base_df(num_bars: int = 100, base_price: float = 100.0) -> pd.DataFrame:
    """Gera um DataFrame determinístico com preços constantes e variações pequenas para testes."""
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(num_bars):
        t = base_time + timedelta(days=i)
        # Candle base: high 101, low 99, close 100, open 100
        rows.append({
            "time": t.strftime("%Y-%m-%d %H:%M:%S"),
            "open": base_price,
            "high": base_price + 1.0,
            "low": base_price - 1.0,
            "close": base_price,
            "tick_volume": 1000,
        })
    return pd.DataFrame(rows)


def test_A_breakout_long_valido():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[-1, df.columns.get_loc("high")] = 105.0
    df.iloc[-1, df.columns.get_loc("close")] = 104.0

    events = strategy.evaluate(df, "XAUUSD", "D1")
    assert len(events) == 1
    evt = events[0]
    assert evt.direction == Direction.BULLISH
    assert evt.reference_price == 101.0  # Upper55
    assert evt.metadata["breakout_level"] == 101.0
    assert evt.metadata["initial_stop"] < 101.0


def test_B_breakout_short_valido():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[-1, df.columns.get_loc("low")] = 95.0
    df.iloc[-1, df.columns.get_loc("close")] = 96.0

    events = strategy.evaluate(df, "XAUUSD", "D1")
    assert len(events) == 1
    evt = events[0]
    assert evt.direction == Direction.BEARISH
    assert evt.reference_price == 99.0  # Lower55
    assert evt.metadata["breakout_level"] == 99.0
    assert evt.metadata["initial_stop"] > 99.0


def test_C_sem_breakout():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    events = strategy.evaluate(df, "XAUUSD", "D1")
    assert len(events) == 0


def test_D_stop_long():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("high")] = 105.0
    events = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")
    assert len(events) == 1
    evt = events[0]
    evt.metadata.pop("exit_lookback", None)  # Foca no teste de Stop Loss

    future = df.iloc[71:].copy()
    future["low"] = 90.0
    future["open"] = 100.0

    sim = simulate_trade_outcome(evt, future, CostsConfig(), full_df=df, entry_index=70)
    assert sim.status == "LOSS"
    assert sim.exit_reason == "STOP"
    assert sim.exit_price == evt.invalidation


def test_E_stop_short():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("low")] = 95.0
    events = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")
    assert len(events) == 1
    evt = events[0]
    evt.metadata.pop("exit_lookback", None)

    future = df.iloc[71:].copy()
    future["high"] = 110.0
    future["open"] = 100.0

    sim = simulate_trade_outcome(evt, future, CostsConfig(), full_df=df, entry_index=70)
    assert sim.status == "LOSS"
    assert sim.exit_reason == "STOP"
    assert sim.exit_price == evt.invalidation


def test_F_donchian_exit_long():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("high")] = 105.0
    events = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")
    evt = events[0]

    future = df.iloc[71:].copy()
    future.iloc[3, future.columns.get_loc("low")] = 98.5

    sim = simulate_trade_outcome(evt, future, CostsConfig(), full_df=df, entry_index=70)
    assert sim.exit_reason == "DONCHIAN_EXIT"
    assert sim.exit_price == 99.0


def test_G_donchian_exit_short():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("low")] = 95.0
    events = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")
    evt = events[0]

    future = df.iloc[71:].copy()
    future.iloc[3, future.columns.get_loc("high")] = 101.5

    sim = simulate_trade_outcome(evt, future, CostsConfig(), full_df=df, entry_index=70)
    assert sim.exit_reason == "DONCHIAN_EXIT"
    assert sim.exit_price == 101.0


def test_H_atr20_correto():
    indicator = ATRIndicator(period=20)
    df = create_base_df(40, 100.0)
    res = indicator.calculate(df)
    assert not pd.isna(res.iloc[20])
    assert res.iloc[20] == pytest.approx(2.0, abs=1e-5)
    assert res.iloc[35] == pytest.approx(2.0, abs=1e-5)


def test_I_ausencia_total_lookahead():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[-1, df.columns.get_loc("high")] = 105.0

    df_with_future = df.copy()

    events1 = strategy.evaluate(df.iloc[:80], "XAUUSD", "D1")
    events2 = strategy.evaluate(df_with_future.iloc[:80], "XAUUSD", "D1")

    assert len(events1) == len(events2) == 1
    assert events1[0].metadata["n_at_entry"] == events2[0].metadata["n_at_entry"]
    assert events1[0].reference_price == events2[0].reference_price


def test_J_warmup_insuficiente():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(50, 100.0)
    df.iloc[-1, df.columns.get_loc("high")] = 110.0
    events = strategy.evaluate(df, "XAUUSD", "D1")
    assert len(events) == 0


def test_K_apenas_uma_posicao_ativa():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(120, 100.0)
    # Define OHLC válido e alto para os candles futuros
    df.loc[77:, "open"] = 102.0
    df.loc[77:, "high"] = 103.0
    df.loc[77:, "low"] = 102.0
    df.loc[77:, "close"] = 103.0

    # Rompimentos nos candles 76 e 82
    df.iloc[76, df.columns.get_loc("high")] = 105.0
    df.iloc[82, df.columns.get_loc("high")] = 110.0

    engine = BacktestEngine(strategy)
    exp = engine.run_experiment(df, "XAUUSD", "D1")
    assert exp.status == "SUCCESS"
    assert len(exp.simulations) == 1




def test_L_end_of_data():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("high")] = 105.0
    events = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")
    evt = events[0]
    evt.metadata.pop("exit_lookback", None)

    future = df.iloc[71:].copy()
    # O preço varia dentro dos limites sem atingir o stop
    sim = simulate_trade_outcome(evt, future, CostsConfig(), full_df=df, entry_index=70)
    assert sim.exit_reason == "END_OF_DATA"


def test_M_custos_alteram_net_mas_nao_gross():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("high")] = 105.0
    evt = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")[0]

    future = df.iloc[71:].copy()
    costs_zero = CostsConfig()
    costs_with_comm = CostsConfig(commission_per_trade=5.0)

    sim_zero = simulate_trade_outcome(evt, future, costs_zero, full_df=df, entry_index=70)
    sim_comm = simulate_trade_outcome(evt, future, costs_with_comm, full_df=df, entry_index=70)

    assert sim_zero.gross_profit == sim_comm.gross_profit
    assert sim_comm.net_profit == sim_zero.net_profit - 5.0


def test_N_resultado_em_multiplos_r_correto():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("high")] = 105.0
    evt = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")[0]

    future = df.iloc[71:].copy()
    sim = simulate_trade_outcome(evt, future, CostsConfig(), full_df=df, entry_index=70)

    initial_risk = evt.metadata["initial_risk"]
    assert sim.r_multiple_gross == pytest.approx(sim.gross_profit / initial_risk)
    assert sim.r_multiple_net == pytest.approx(sim.net_profit / initial_risk)


def test_O_gap_na_entrada():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[-1, df.columns.get_loc("open")] = 107.0
    df.iloc[-1, df.columns.get_loc("high")] = 108.0

    events = strategy.evaluate(df, "XAUUSD", "D1")
    assert len(events) == 1
    evt = events[0]
    assert evt.reference_price == 107.0


def test_P_gap_atravessando_stop():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("high")] = 105.0
    evt = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")[0]
    evt.metadata.pop("exit_lookback", None)

    future = df.iloc[71:].copy()
    future.iloc[0, future.columns.get_loc("open")] = 90.0
    future.iloc[0, future.columns.get_loc("low")] = 89.0

    sim = simulate_trade_outcome(evt, future, CostsConfig(), full_df=df, entry_index=70)
    assert sim.exit_reason == "STOP"
    assert sim.exit_price == 90.0


def test_Q_gap_atravessando_donchian_exit():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("high")] = 105.0
    evt = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")[0]

    future = df.iloc[71:].copy()
    evt.invalidation = 80.0
    future.iloc[0, future.columns.get_loc("open")] = 95.0
    future.iloc[0, future.columns.get_loc("low")] = 94.0

    sim = simulate_trade_outcome(evt, future, CostsConfig(), full_df=df, entry_index=70)
    assert sim.exit_reason == "DONCHIAN_EXIT"
    assert sim.exit_price == 95.0


def test_R_entrada_e_stop_possiveis_na_mesma_barra():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[70, df.columns.get_loc("high")] = 105.0
    evt = strategy.evaluate(df.iloc[:71], "XAUUSD", "D1")[0]
    evt.metadata.pop("exit_lookback", None)

    future = df.iloc[71:].copy()
    future.iloc[0, future.columns.get_loc("low")] = 90.0

    sim = simulate_trade_outcome(evt, future, CostsConfig(), policy=IntrabarPolicy.CONSERVATIVE, full_df=df, entry_index=70)
    assert sim.status == "LOSS"
    assert sim.exit_reason == "STOP"


def test_S_dual_breakout():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)

    # Caso A: open=100.0 (entre 99 e 101), high=105, low=90 -> Rejeitado como AMBIGUOUS_DUAL_BREAKOUT
    df.iloc[-1, df.columns.get_loc("open")] = 100.0
    df.iloc[-1, df.columns.get_loc("high")] = 105.0
    df.iloc[-1, df.columns.get_loc("low")] = 90.0

    events_a = strategy.evaluate(df, "XAUUSD", "D1")
    assert len(events_a) == 0
    assert strategy.ambiguous_events_count == 1

    # Caso B: open=106.0 (gap acima de Upper55=101), high=107, low=90 -> Long ativado no open
    df_b = create_base_df(80, 100.0)
    df_b.iloc[-1, df.columns.get_loc("open")] = 106.0
    df_b.iloc[-1, df.columns.get_loc("high")] = 107.0
    df_b.iloc[-1, df.columns.get_loc("low")] = 90.0

    events_b = strategy.evaluate(df_b, "XAUUSD", "D1")
    assert len(events_b) == 1
    assert events_b[0].direction == Direction.BULLISH
    assert events_b[0].reference_price == 106.0


def test_T_lookahead_n_at_entry():
    strategy = HagmartkTrendReferenceStrategy()
    df = create_base_df(80, 100.0)
    df.iloc[-1, df.columns.get_loc("high")] = 105.0

    events_orig = strategy.evaluate(df.copy(), "XAUUSD", "D1")
    n_orig = events_orig[0].metadata["n_at_entry"]

    # Modificar artificialmente high e close sem romper o low (evita dual breakout)
    df_mod = df.copy()
    df_mod.iloc[-1, df_mod.columns.get_loc("high")] = 150.0
    df_mod.iloc[-1, df_mod.columns.get_loc("close")] = 140.0

    events_mod = strategy.evaluate(df_mod, "XAUUSD", "D1")
    n_mod = events_mod[0].metadata["n_at_entry"]

    assert n_orig == n_mod
