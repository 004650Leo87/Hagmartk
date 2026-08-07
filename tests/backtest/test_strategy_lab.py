from datetime import datetime, timedelta, timezone
from typing import List, Optional
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.backtest.data_quality import DataQualityReport, validate_data_quality
from backend.backtest.engine import BacktestEngine
from backend.backtest.metrics import calculate_metrics
from backend.backtest.simulator import CostsConfig, IntrabarPolicy, TradeSimulation, simulate_trade_outcome
from backend.domain.events import Direction, StrategyEvent
from backend.strategies.base import BaseStrategy, BenchmarkSMAStrategy, StrategyRegistry


def generate_synthetic_candles(num_bars: int = 60, trend: str = "UP") -> pd.DataFrame:
    """Gera um DataFrame determinístico de candles para testes automatizados."""
    base_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    data = []
    price = 100.0

    for i in range(num_bars):
        time_val = base_time + timedelta(minutes=15 * i)
        if trend == "UP":
            open_p = price
            close_p = price + 1.0
            high_p = close_p + 0.5
            low_p = open_p - 0.5
            price = close_p
        elif trend == "DOWN":
            open_p = price
            close_p = price - 1.0
            high_p = open_p + 0.5
            low_p = close_p - 0.5
            price = close_p
        else:  # OSCILLATE
            delta = 1.0 if i % 2 == 0 else -1.0
            open_p = price
            close_p = price + delta
            high_p = max(open_p, close_p) + 0.5
            low_p = min(open_p, close_p) - 0.5
            price = close_p

        data.append(
            {
                "time": time_val.isoformat(),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "tick_volume": 100 + i,
                "spread": 1,
                "real_volume": 10,
            }
        )

    return pd.DataFrame(data)


class LookaheadInspectorStrategy(BaseStrategy):
    """Estratégia de auditoria para provar zero lookahead bias nos testes."""

    def __init__(self) -> None:
        self.strategy_id = "LOOKAHEAD_INSPECTOR"
        self.name = "Lookahead Inspector"
        self.version = "1.0"
        self.description = "Audit strategy for zero lookahead bias"
        self.allowed_timeframes = ["M15"]
        self.parameters = {}
        self.warmup_bars = 10
        self.allow_open_candle = False
        self.evaluated_histories: List[str] = []

    def evaluate(
        self,
        history: pd.DataFrame,
        symbol: str,
        timeframe: str,
        is_closed_bar: bool = True,
    ) -> List[StrategyEvent]:
        # Registra a hora do último candle disponível na fatia recebida
        last_time = str(history["time"].iloc[-1])
        self.evaluated_histories.append(last_time)

        # Prova de zero lookahead bias: a fatia de histórico recebida não pode conter tempos maiores que last_time
        times = list(history["time"])
        assert max(times) == last_time

        return []


def test_a_and_b_zero_lookahead_bias_and_future_candle_unaccessibility():
    """PROVA A e B: A estratégia só recebe fatias contendo dados até a barra T no instante da decisão."""
    df = generate_synthetic_candles(num_bars=40, trend="UP")
    audit_strat = LookaheadInspectorStrategy()

    engine = BacktestEngine(strategy=audit_strat)
    exp = engine.run_experiment(df=df, symbol="EURUSD", timeframe="M15")

    assert exp.status == "SUCCESS"
    # warmup_bars=10, barras=40 -> 40 - 10 - 1 = 29 avaliações bar-by-bar
    assert len(audit_strat.evaluated_histories) == 29

    # Garante ordem estritamente crescente das janelas recebidas a cada passo
    for i in range(1, len(audit_strat.evaluated_histories)):
        assert audit_strat.evaluated_histories[i] > audit_strat.evaluated_histories[i - 1]


def test_c_chronological_order_and_invalid_data():
    """PROVA C e K: Detecção de dados sem ordem cronológica ou com OHLC inconsistente."""
    df = generate_synthetic_candles(num_bars=30)

    # Inverte 2 linhas para quebrar a ordem cronológica
    df_invalid_time = df.copy()
    df_invalid_time.loc[15, "time"], df_invalid_time.loc[16, "time"] = (
        df_invalid_time.loc[16, "time"],
        df_invalid_time.loc[15, "time"],
    )

    report = validate_data_quality(df_invalid_time, warmup_bars=10, min_eval_bars=5)
    assert report.is_valid is False
    assert report.chronological_violations_count > 0

    # Inconsistência de OHLC (low > high)
    df_invalid_ohlc = df.copy()
    df_invalid_ohlc.loc[10, "low"] = 500.0  # low maior que high
    report_ohlc = validate_data_quality(df_invalid_ohlc, warmup_bars=10, min_eval_bars=5)
    assert report_ohlc.is_valid is False
    assert report_ohlc.invalid_ohlc_count > 0


def test_d_allowed_timeframes_restriction():
    """PROVA D: Rejeição de backtest em timeframe não autorizado pela estratégia."""
    strat = BenchmarkSMAStrategy(allowed_timeframes=["M15", "H1"])
    engine = BacktestEngine(strategy=strat)
    df = generate_synthetic_candles(num_bars=50)

    # Execução em timeframe não permitido (M5)
    exp_rejected = engine.run_experiment(df=df, symbol="XAUUSD", timeframe="M5")
    assert exp_rejected.status == "REJECTED_TIMEFRAME"

    # Execução em timeframe permitido (M15)
    exp_success = engine.run_experiment(df=df, symbol="XAUUSD", timeframe="M15")
    assert exp_success.status == "SUCCESS"


def test_e_warmup_bars_exclusion():
    """PROVA E: Os candles de warmup são excluídos do acionamento de ocorrências."""
    df = generate_synthetic_candles(num_bars=50, trend="OSCILLATE")
    strat = BenchmarkSMAStrategy(fast_period=5, slow_period=10)
    strat.warmup_bars = 25  # Força warmup de 25 barras

    engine = BacktestEngine(strategy=strat)
    exp = engine.run_experiment(df=df, symbol="EURUSD", timeframe="M15")

    assert exp.status == "SUCCESS"
    for sim in exp.simulations:
        # Nenhum trade pode ser detectado antes do fim do warmup
        assert sim.event.detected_at >= str(df["time"].iloc[25])


def test_f_metrics_calculation():
    """PROVA F: Cálculo exato das estatísticas quantitativas (Win Rate, Profit Factor, Drawdown, Payoff)."""
    evt1 = StrategyEvent(
        strategy_id="TEST",
        strategy_version="1.0",
        symbol="EURUSD",
        timeframe="M15",
        direction=Direction.BUY,
        detected_at="2026-01-01T10:00:00",
        reference_price=100.0,
    )
    t1 = TradeSimulation(trade_id="1", event=evt1, intrabar_policy=IntrabarPolicy.CONSERVATIVE, costs=CostsConfig())
    t1.net_profit = 20.0
    t1.duration_bars = 5

    t2 = TradeSimulation(trade_id="2", event=evt1, intrabar_policy=IntrabarPolicy.CONSERVATIVE, costs=CostsConfig())
    t2.net_profit = -10.0
    t2.duration_bars = 3

    t3 = TradeSimulation(trade_id="3", event=evt1, intrabar_policy=IntrabarPolicy.CONSERVATIVE, costs=CostsConfig())
    t3.net_profit = 30.0
    t3.duration_bars = 4

    metrics = calculate_metrics([t1, t2, t3])
    assert metrics.total_trades == 3
    assert metrics.wins == 2
    assert metrics.losses == 1
    assert abs(metrics.win_rate - (2 / 3)) < 1e-4
    assert metrics.gross_profit == 50.0
    assert metrics.gross_loss == 10.0
    assert metrics.net_result == 40.0
    assert metrics.profit_factor == 5.0  # 50 / 10
    assert metrics.average_win == 25.0
    assert metrics.average_loss == 10.0
    assert metrics.payoff_ratio == 2.5
    assert metrics.max_drawdown == 10.0


def test_g_intrabar_ambiguity_policy():
    """PROVA G: Tratamento de ambiguidade quando Stop e Alvo são tocados no mesmo candle."""
    evt = StrategyEvent(
        strategy_id="TEST",
        strategy_version="1.0",
        symbol="EURUSD",
        timeframe="M15",
        direction=Direction.BUY,
        detected_at="2026-01-01T10:00:00",
        reference_price=100.0,
        invalidation=95.0,
        targets=[105.0],
    )

    # Candle futuro onde a máxima é 106 (alvo) e a mínima é 94 (stop)
    future_candles = pd.DataFrame(
        [
            {
                "time": "2026-01-01T10:15:00",
                "open": 100.0,
                "high": 106.0,
                "low": 94.0,
                "close": 98.0,
            }
        ]
    )

    # 1. Política Conservadora -> STOP é assumido em primeiro lugar
    sim_cons = simulate_trade_outcome(evt, future_candles, CostsConfig(), policy=IntrabarPolicy.CONSERVATIVE)
    assert sim_cons.status == "LOSS"
    assert sim_cons.exit_price == 95.0
    assert sim_cons.intrabar_conflict_resolved is True

    # 2. Política Otimista -> TARGET é assumido em primeiro lugar
    sim_opt = simulate_trade_outcome(evt, future_candles, CostsConfig(), policy=IntrabarPolicy.OPTIMISTIC)
    assert sim_opt.status == "WIN"
    assert sim_opt.exit_price == 105.0
    assert sim_opt.intrabar_conflict_resolved is True


def test_h_and_i_metrics_aggregation_by_symbol_and_timeframe():
    """PROVA H e I: Agregação correta de estatísticas por símbolo e timeframe."""
    evt_eur = StrategyEvent("S1", "1.0", "EURUSD", "M15", Direction.BUY, "2026-01-01T10:00:00", 1.10)
    evt_xau = StrategyEvent("S1", "1.0", "XAUUSD", "H1", Direction.SELL, "2026-01-01T11:00:00", 2000.0)

    t1 = TradeSimulation("1", evt_eur, IntrabarPolicy.CONSERVATIVE, CostsConfig())
    t1.net_profit = 15.0

    t2 = TradeSimulation("2", evt_xau, IntrabarPolicy.CONSERVATIVE, CostsConfig())
    t2.net_profit = -5.0

    metrics = calculate_metrics([t1, t2])
    assert "EURUSD" in metrics.by_symbol
    assert "XAUUSD" in metrics.by_symbol
    assert metrics.by_symbol["EURUSD"]["net_result"] == 15.0
    assert metrics.by_symbol["XAUUSD"]["net_result"] == -5.0

    assert "M15" in metrics.by_timeframe
    assert "H1" in metrics.by_timeframe


def test_j_insufficient_history_handling():
    """PROVA J: Rejeição limpa quando o histórico é menor que o mínimo necessário."""
    df_short = generate_synthetic_candles(num_bars=5)
    report = validate_data_quality(df_short, warmup_bars=10, min_eval_bars=10)
    assert report.is_valid is False
    assert report.status == "INSUFFICIENT_HISTORY"


def test_l_error_isolation_in_multi_asset_backtest():
    """PROVA L: Isolamento de erro entre ativos na execução multi-asset."""
    df_good = generate_synthetic_candles(num_bars=50)
    df_bad = pd.DataFrame()  # Vazio

    data_map = {"EURUSD": df_good, "INVALID_ASSET": df_bad}
    strat = BenchmarkSMAStrategy()

    results = BacktestEngine.run_multi_asset(
        strategy=strat,
        data_by_symbol=data_map,
        timeframe="M15",
    )

    assert len(results) == 2
    assert results["EURUSD"].status == "SUCCESS"
    assert results["INVALID_ASSET"].status == "FAILED_DATA_QUALITY"


def test_strategy_lab_api_endpoints():
    """Testa a integração das rotas HTTP do Strategy Lab via TestClient."""
    StrategyRegistry.register(BenchmarkSMAStrategy())
    client = TestClient(app)

    # 1. GET /api/strategies
    res = client.get("/api/strategies")
    assert res.status_code == 200
    strats = res.json()
    assert isinstance(strats, list)
    assert any(s["strategy_id"] == "BENCHMARK_SMA" for s in strats)

    # 2. GET /api/strategies/BENCHMARK_SMA
    res_det = client.get("/api/strategies/BENCHMARK_SMA")
    assert res_det.status_code == 200
    assert res_det.json()["strategy_id"] == "BENCHMARK_SMA"

    # 3. GET /api/strategies/NONEXISTENT -> 404
    res_404 = client.get("/api/strategies/NONEXISTENT")
    assert res_404.status_code == 404
