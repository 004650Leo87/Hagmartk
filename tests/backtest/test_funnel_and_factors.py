from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from backend.backtest.data_cache import OHLCDataCache
from backend.backtest.funnel import FunnelPromotionCriteria, Stage1ScreeningResult, evaluate_stage1_screening
from backend.domain.event_study import EventStudyEngine, EventStudyRecord
from backend.indicators.atr import ATRIndicator
from backend.indicators.rsi import RSIIndicator
from backend.indicators.vectorized import (
    calculate_vectorized_atr,
    calculate_vectorized_donchian,
    calculate_vectorized_rsi,
)
from backend.strategies.factor_pipeline import FactorCombinationConfig, FactorPipelineStrategy
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy


def create_test_df(num_bars: int = 150) -> pd.DataFrame:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    price = 100.0
    for i in range(num_bars):
        t = base + timedelta(days=i)
        price += (i % 3 - 1) * 0.5
        rows.append({
            "time": t.strftime("%Y-%m-%d %H:%M:%S"),
            "open": price,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price + 0.2,
            "tick_volume": 1000,
        })
    return pd.DataFrame(rows)


def test_1_data_cache_hash_integrity():
    cache = OHLCDataCache(cache_dir="scratch/test_cache")
    df = create_test_df(100)
    meta = cache.save(df, "EURUSD", "D1")

    assert meta.dataset_hash != ""

    loaded_df, loaded_meta = cache.load("EURUSD", "D1")
    assert loaded_df is not None
    assert loaded_meta.dataset_hash == meta.dataset_hash
    assert len(loaded_df) == 100


def test_2_vectorized_indicator_equivalence():
    df = create_test_df(150)

    # Equivalência de ATR
    ref_atr = ATRIndicator(period=20).calculate(df)
    vec_atr = calculate_vectorized_atr(df, period=20)
    pd.testing.assert_series_equal(ref_atr, vec_atr)

    # Equivalência de RSI
    ref_rsi = RSIIndicator(period=14).calculate(df)
    vec_rsi = calculate_vectorized_rsi(df, period=14)
    pd.testing.assert_series_equal(ref_rsi, vec_rsi)

    # Equivalência de Donchian (sem Lookahead)
    u_ent, l_ent, u_ex, l_ex = calculate_vectorized_donchian(df, entry_period=55, exit_period=20)
    assert len(u_ent) == len(df)
    expected_u_55 = df["high"].iloc[:55].max()
    assert u_ent.iloc[55] == expected_u_55


def test_3_stage1_screening_and_promotion_criteria():
    criteria = FunnelPromotionCriteria(min_trades=10, min_profit_factor=1.1, enabled=True)
    df = create_test_df(100)

    from backend.backtest.simulator import CostsConfig, IntrabarPolicy, TradeSimulation
    from backend.domain.events import Direction, StrategyEvent

    evt = StrategyEvent("TEST", "1.0", "EURUSD", "D1", Direction.BUY, "2026-01-01", 100.0, invalidation=95.0)

    # Rejeitado por poucos trades
    sims_few = [TradeSimulation("1", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=10.0, r_multiple_net=1.0)]
    res_rejected = evaluate_stage1_screening(sims_few, "EURUSD", "FOREX", "D1", 1.0, criteria)
    assert res_rejected.promoted_to_stage2 is False
    assert len(res_rejected.rejection_reasons) > 0

    # Aprovado com trades e PF suficientes
    sims_good = [
        TradeSimulation(f"{i}", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=15.0 if i % 2 == 0 else -5.0, r_multiple_net=1.5 if i % 2 == 0 else -0.5)
        for i in range(12)
    ]
    res_promoted = evaluate_stage1_screening(sims_good, "EURUSD", "FOREX", "D1", 1.0, criteria)
    assert res_promoted.promoted_to_stage2 is True


def test_4_event_study_record_and_engine():
    df = create_test_df(100)
    base_events = [{"name": "TEST_EVENT", "time": df["time"].iloc[10], "price": df["close"].iloc[10]}]

    def mock_evaluator(sub_df, evt):
        return len(sub_df) >= 15

    records = EventStudyEngine.analyze_event_sequence(df, base_events, confirmation_evaluator_fn=mock_evaluator)
    assert len(records) == 1
    rec = records[0]
    assert rec.base_event_time == df["time"].iloc[10]
    assert rec.confirmed_at == df["time"].iloc[14]
    assert rec.bars_to_secondary_event == 4


def test_5_factor_pipeline_strategy_architecture():
    cfg = FactorCombinationConfig(name="DVAP_DIDI", use_dvap=True, use_didi=True)
    strat = FactorPipelineStrategy(cfg)
    assert strat.strategy_id == "factor_pipeline_dvap_didi"
    assert strat.parameters["use_dvap"] is True
    assert strat.parameters["use_didi"] is True


def test_6_cache_integrity_edge_cases():
    cache = OHLCDataCache(cache_dir="scratch/test_cache")
    df = create_test_df(100)
    meta = cache.save(df, "GBPUSD", "H1")

    # A. save -> load preserva dataset_hash
    loaded_df, loaded_meta = cache.load("GBPUSD", "H1")
    assert loaded_df is not None
    assert loaded_meta.dataset_hash == meta.dataset_hash

    # B. Float round-trip não gera falso corruption ao salvar/carregar
    loaded_hash = cache.compute_dataset_hash(loaded_df)
    assert loaded_hash == meta.dataset_hash

    # C. Alteração real no OHLC altera o hash
    df_mod = loaded_df.copy()
    df_mod.loc[0, "close"] += 999.0
    mod_hash = cache.compute_dataset_hash(df_mod)
    assert mod_hash != meta.dataset_hash

    # D. Dataset alterado é rejeitado com hash esperado
    rejected_df, _ = cache.load("GBPUSD", "H1", expected_hash="wrong_hash")
    assert rejected_df is None
