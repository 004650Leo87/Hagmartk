from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.domain.events import Direction, StrategyEvent
from backend.strategies.hdf.models import HDFOccurrence


class ExitPolicyType(Enum):
    FIXED_TARGET = "FIXED_TARGET"
    PARTIAL_RUNNER = "PARTIAL_RUNNER"
    TIME_EXIT = "TIME_EXIT"


@dataclass
class ExitPolicyConfig:
    name: str
    policy_type: ExitPolicyType
    target_r: Optional[float] = None
    partial_pct: float = 0.0
    partial_target_r: Optional[float] = None
    runner_target_r: Optional[float] = None
    time_horizon_bars: Optional[int] = None
    intrabar_policy: str = "STOP_FIRST"


@dataclass
class TradeExitResult:
    occurrence_id: str
    symbol: str
    asset_class: str
    timeframe: str
    pattern_type: str
    volume_bucket: str
    direction: str
    session: str

    entry_price: float
    initial_stop: float
    initial_risk: float

    status: str  # "WIN", "LOSS", "OPEN", "PARTIAL_WIN"
    exit_reason: str  # "STOP", "TARGET", "PARTIAL_RUNNER", "TIME_EXIT"

    gross_r: float
    costs_r: float
    net_r: float

    holding_bars: int
    stopped: bool
    target_hit: bool


@dataclass
class ExitPolicyMetrics:
    policy_name: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    open_trades: int = 0
    win_rate: float = 0.0

    gross_r: float = 0.0
    costs_r: float = 0.0
    net_r: float = 0.0
    expectancy_r: float = 0.0
    median_r: float = 0.0
    profit_factor_r: float = 0.0

    average_win_r: float = 0.0
    average_loss_r: float = 0.0
    payoff_ratio: float = 0.0

    max_drawdown_r: float = 0.0
    max_consecutive_losses: int = 0

    average_holding_bars: float = 0.0
    median_holding_bars: float = 0.0

    stop_rate: float = 0.0
    target_hit_rate: float = 0.0
    cross_context_score: int = 0  # Quantidade de sub-contextos (3 TFs x 3 Classes) com Expectancy_R > 0


def simulate_exit_policy_on_occurrence(
    occ: HDFOccurrence,
    df_future: pd.DataFrame,
    cfg: ExitPolicyConfig,
    cost_per_trade_r: float = 0.03,  # Custo fixo estimado em fração de R (spread + slippage)
) -> TradeExitResult:
    """Simula uma política de saída sobre uma ocorrência ativada sem modificar os parâmetros de entrada."""
    occ_id = occ.occurrence_id
    symbol = occ.symbol
    timeframe = occ.timeframe
    direction = occ.direction
    pat_str = occ.pattern_type.value if hasattr(occ.pattern_type, "value") else str(occ.pattern_type)
    vol_bkt = occ.relative_volume_bucket
    sess_str = occ.session.value if hasattr(occ.session, "value") else str(occ.session)

    asset_class = "FOREX" if symbol in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"] else ("METALS" if symbol in ["XAUUSD", "XAGUSD"] else "CRYPTO")

    entry_price = occ.entry_price
    initial_stop = occ.initial_stop
    init_risk = occ.initial_risk
    if init_risk <= 0.0:
        init_risk = abs(entry_price - initial_stop)

    is_buy = (direction == "BULLISH")
    n_fwd = len(df_future)

    highs = df_future["high"].values if n_fwd > 0 else np.array([])
    lows = df_future["low"].values if n_fwd > 0 else np.array([])
    closes = df_future["close"].values if n_fwd > 0 else np.array([])

    res = TradeExitResult(
        occurrence_id=occ_id,
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        pattern_type=pat_str,
        volume_bucket=vol_bkt,
        direction=direction,
        session=sess_str,
        entry_price=entry_price,
        initial_stop=initial_stop,
        initial_risk=init_risk,
        status="OPEN",
        exit_reason="OPEN",
        gross_r=0.0,
        costs_r=cost_per_trade_r,
        net_r=-cost_per_trade_r,
        holding_bars=min(20, n_fwd),
        stopped=False,
        target_hit=False,
    )

    if n_fwd == 0 or init_risk <= 0.0:
        return res

    # ----------------------------------------------------
    # 1. POLÍTICA DE TARGET FIXO
    # ----------------------------------------------------
    if cfg.policy_type == ExitPolicyType.FIXED_TARGET:
        target_r = cfg.target_r or 1.0
        target_price = (entry_price + target_r * init_risk) if is_buy else (entry_price - target_r * init_risk)

        for step in range(n_fwd):
            h_p, l_p = highs[step], lows[step]
            stop_hit = (l_p <= initial_stop) if is_buy else (h_p >= initial_stop)
            target_hit = (h_p >= target_price) if is_buy else (l_p <= target_price)

            if stop_hit and target_hit:
                # Conflito intrabar: Política conservadora STOP_FIRST
                res.status = "LOSS"
                res.exit_reason = "STOP"
                res.gross_r = -1.0
                res.stopped = True
                res.holding_bars = step + 1
                break
            elif stop_hit:
                res.status = "LOSS"
                res.exit_reason = "STOP"
                res.gross_r = -1.0
                res.stopped = True
                res.holding_bars = step + 1
                break
            elif target_hit:
                res.status = "WIN"
                res.exit_reason = "TARGET"
                res.gross_r = target_r
                res.target_hit = True
                res.holding_bars = step + 1
                break
        else:
            # Se não encerrou por stop nem target no horizonte disponível
            res.status = "OPEN"
            res.exit_reason = "END_OF_DATA"
            c_p = closes[-1]
            pnl_r = ((c_p - entry_price) / init_risk) if is_buy else ((entry_price - c_p) / init_risk)
            res.gross_r = pnl_r
            res.holding_bars = n_fwd

    # ----------------------------------------------------
    # 2. POLÍTICA DE SAÍDA PARCIAL
    # ----------------------------------------------------
    elif cfg.policy_type == ExitPolicyType.PARTIAL_RUNNER:
        p_pct = cfg.partial_pct or 0.5
        r_pct = 1.0 - p_pct
        p_target_r = cfg.partial_target_r or 1.0
        run_target_r = cfg.runner_target_r or 2.0

        p_target_price = (entry_price + p_target_r * init_risk) if is_buy else (entry_price - p_target_r * init_risk)
        run_target_price = (entry_price + run_target_r * init_risk) if is_buy else (entry_price - run_target_r * init_risk)

        partial_taken = False
        partial_r = 0.0
        runner_r = 0.0

        for step in range(n_fwd):
            h_p, l_p = highs[step], lows[step]
            stop_hit = (l_p <= initial_stop) if is_buy else (h_p >= initial_stop)

            if not partial_taken:
                p_target_hit = (h_p >= p_target_price) if is_buy else (l_p <= p_target_price)
                if stop_hit and p_target_hit:
                    res.status = "LOSS"
                    res.exit_reason = "STOP"
                    res.gross_r = -1.0
                    res.stopped = True
                    res.holding_bars = step + 1
                    break
                elif stop_hit:
                    res.status = "LOSS"
                    res.exit_reason = "STOP"
                    res.gross_r = -1.0
                    res.stopped = True
                    res.holding_bars = step + 1
                    break
                elif p_target_hit:
                    partial_taken = True
                    partial_r = p_target_r
                    res.target_hit = True

                    # Checa se o runner também foi atingido no mesmo candle
                    run_target_hit = (h_p >= run_target_price) if is_buy else (l_p <= run_target_price)
                    if run_target_hit:
                        runner_r = run_target_r
                        res.status = "WIN"
                        res.exit_reason = "PARTIAL_RUNNER"
                        res.gross_r = p_pct * partial_r + r_pct * runner_r
                        res.holding_bars = step + 1
                        break
            else:
                # Runner ativo
                run_target_hit = (h_p >= run_target_price) if is_buy else (l_p <= run_target_price)
                if stop_hit and run_target_hit:
                    # STOP_FIRST no runner
                    runner_r = -1.0
                    res.status = "WIN" if (p_pct * partial_r + r_pct * runner_r) > 0 else "LOSS"
                    res.exit_reason = "RUNNER_STOPPED"
                    res.gross_r = p_pct * partial_r + r_pct * runner_r
                    res.holding_bars = step + 1
                    break
                elif stop_hit:
                    runner_r = -1.0
                    res.status = "WIN" if (p_pct * partial_r + r_pct * runner_r) > 0 else "LOSS"
                    res.exit_reason = "RUNNER_STOPPED"
                    res.gross_r = p_pct * partial_r + r_pct * runner_r
                    res.holding_bars = step + 1
                    break
                elif run_target_hit:
                    runner_r = run_target_r
                    res.status = "WIN"
                    res.exit_reason = "PARTIAL_RUNNER"
                    res.gross_r = p_pct * partial_r + r_pct * runner_r
                    res.holding_bars = step + 1
                    break
        else:
            res.status = "OPEN"
            res.exit_reason = "END_OF_DATA"
            c_p = closes[-1]
            pnl_runner = ((c_p - entry_price) / init_risk) if is_buy else ((entry_price - c_p) / init_risk)
            if partial_taken:
                res.gross_r = p_pct * partial_r + r_pct * pnl_runner
            else:
                res.gross_r = pnl_runner
            res.holding_bars = n_fwd

    # ----------------------------------------------------
    # 3. POLÍTICA DE SAÍDA POR TEMPO (TIME EXIT)
    # ----------------------------------------------------
    elif cfg.policy_type == ExitPolicyType.TIME_EXIT:
        horizon = cfg.time_horizon_bars or 5
        horizon_step = min(horizon, n_fwd) - 1

        for step in range(horizon_step + 1):
            h_p, l_p = highs[step], lows[step]
            stop_hit = (l_p <= initial_stop) if is_buy else (h_p >= initial_stop)
            if stop_hit:
                res.status = "LOSS"
                res.exit_reason = "STOP"
                res.gross_r = -1.0
                res.stopped = True
                res.holding_bars = step + 1
                break
            c_p = closes[horizon_step]
            if is_buy:
                res.status = "WIN" if c_p > entry_price else "LOSS"
            else:
                res.status = "WIN" if c_p < entry_price else "LOSS"
            res.exit_reason = "TIME_EXIT"
            res.gross_r = ((c_p - entry_price) / init_risk) if is_buy else ((entry_price - c_p) / init_risk)
            res.holding_bars = horizon_step + 1

    res.net_r = res.gross_r - res.costs_r
    return res


def calculate_exit_policy_metrics(
    results: List[TradeExitResult], policy_name: str
) -> ExitPolicyMetrics:
    """Calcula estatísticas agregadas e reconciliadas para uma política de saída."""
    metrics = ExitPolicyMetrics(policy_name=policy_name)
    if not results:
        return metrics

    n = len(results)
    metrics.total_trades = n

    wins = [r for r in results if r.net_r > 0]
    losses = [r for r in results if r.net_r <= 0 and r.status != "OPEN"]
    opens = [r for r in results if r.status == "OPEN"]

    metrics.wins = len(wins)
    metrics.losses = len(losses)
    metrics.open_trades = len(opens)
    metrics.win_rate = (metrics.wins / n * 100.0) if n > 0 else 0.0

    metrics.gross_r = float(np.sum([r.gross_r for r in results]))
    metrics.costs_r = float(np.sum([r.costs_r for r in results]))
    metrics.net_r = float(np.sum([r.net_r for r in results]))

    net_rs = [r.net_r for r in results]
    metrics.expectancy_r = float(np.mean(net_rs)) if net_rs else 0.0
    metrics.median_r = float(np.median(net_rs)) if net_rs else 0.0

    w_sum = sum(r.net_r for r in wins)
    l_sum = abs(sum(r.net_r for r in losses))
    metrics.profit_factor_r = float(w_sum / l_sum) if l_sum > 0 else (float(w_sum) if w_sum > 0 else 0.0)

    metrics.average_win_r = float(np.mean([r.net_r for r in wins])) if wins else 0.0
    metrics.average_loss_r = float(np.mean([abs(r.net_r) for r in losses])) if losses else 0.0
    metrics.payoff_ratio = (metrics.average_win_r / metrics.average_loss_r) if metrics.average_loss_r > 0 else 0.0

    # Max Drawdown em R
    eq = np.cumsum([0.0] + net_rs)
    pk = np.maximum.accumulate(eq)
    dd = pk - eq
    metrics.max_drawdown_r = float(np.max(dd))

    # Consecutivos Loss
    max_cons = 0
    curr_cons = 0
    for r in results:
        if r.net_r <= 0:
            curr_cons += 1
            if curr_cons > max_cons:
                max_cons = curr_cons
        else:
            curr_cons = 0
    metrics.max_consecutive_losses = max_cons

    holdings = [r.holding_bars for r in results]
    metrics.average_holding_bars = float(np.mean(holdings)) if holdings else 0.0
    metrics.median_holding_bars = float(np.median(holdings)) if holdings else 0.0

    metrics.stop_rate = (sum(1 for r in results if r.stopped) / n * 100.0) if n > 0 else 0.0
    metrics.target_hit_rate = (sum(1 for r in results if r.target_hit) / n * 100.0) if n > 0 else 0.0

    # Cross Context Score (grupos de TF x Classe com Expectancy_R > 0)
    groups = defaultdict(list)
    for r in results:
        groups[f"{r.asset_class}_{r.timeframe}"].append(r.net_r)

    score = 0
    for g_key, g_rs in groups.items():
        if np.mean(g_rs) > 0.0:
            score += 1
    metrics.cross_context_score = score

    return metrics
