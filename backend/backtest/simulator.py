from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import pandas as pd

from backend.domain.events import Direction, StrategyEvent


class IntrabarPolicy(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"  # STOP_FIRST quando stop e alvo são tocados na mesma barra
    OPTIMISTIC = "OPTIMISTIC"      # TARGET_FIRST quando stop e alvo são tocados na mesma barra
    STOP_FIRST = "STOP_FIRST"
    TARGET_FIRST = "TARGET_FIRST"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class CostsConfig:
    spread_points: float = 0.0
    point_value: float = 0.00001
    commission_per_trade: float = 0.0
    slippage_points: float = 0.0
    swap_per_bar: float = 0.0


@dataclass
class TradeSimulation:
    trade_id: str
    event: StrategyEvent
    intrabar_policy: IntrabarPolicy
    costs: CostsConfig
    status: str = "OPEN"  # "WIN", "LOSS", "BREAKEVEN", "OPEN", "CANCELLED"
    entry_price: float = 0.0
    exit_price: float = 0.0
    entry_time: str = ""
    exit_time: str = ""
    duration_bars: int = 0
    gross_profit: float = 0.0
    net_profit: float = 0.0
    mae: float = 0.0  # Maximum Adverse Excursion
    mfe: float = 0.0  # Maximum Favorable Excursion
    hit_target_index: Optional[int] = None
    intrabar_conflict_resolved: bool = False
    exit_reason: str = ""  # "STOP", "DONCHIAN_EXIT", "END_OF_DATA", "TARGET"
    initial_risk: float = 0.0
    r_multiple_gross: float = 0.0
    r_multiple_net: float = 0.0


def simulate_trade_outcome(
    event: StrategyEvent,
    future_candles: pd.DataFrame,
    costs: CostsConfig,
    policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE,
    full_df: Optional[pd.DataFrame] = None,
    entry_index: Optional[int] = None,
) -> TradeSimulation:
    """Simula a execução e o desfecho de um StrategyEvent sobre a sequência cronológica de candles futuros.

    REQUISITO FUNDAMENTAL: ZERO LOOKAHEAD BIAS.
    future_candles contém estritamente as barras T+1, T+2, ... após o disparo da decisão.
    """
    trade = TradeSimulation(
        trade_id=f"{event.strategy_id}_{event.symbol}_{event.detected_at}",
        event=event,
        intrabar_policy=policy,
        costs=costs,
    )

    if future_candles is None or future_candles.empty:
        trade.status = "OPEN"
        trade.exit_reason = "END_OF_DATA"
        return trade

    direction = event.direction
    is_buy = direction in (Direction.BUY, Direction.BULLISH)
    entry_price = event.reference_price
    if event.entry_zone and len(event.entry_zone) == 2:
        entry_price = (event.entry_zone[0] + event.entry_zone[1]) / 2.0

    stop_price = event.invalidation
    targets = event.targets or []
    exit_lookback = event.metadata.get("exit_lookback")

    # Ajuste de entrada por derrapagem (slippage)
    slippage_offset = costs.slippage_points * costs.point_value
    if is_buy:
        entry_price += slippage_offset
    else:
        entry_price -= slippage_offset

    trade.entry_price = entry_price
    trade.entry_time = str(future_candles["time"].iloc[0])

    initial_risk = event.metadata.get("initial_risk")
    if initial_risk is None and stop_price is not None:
        initial_risk = abs(entry_price - stop_price)
    trade.initial_risk = float(initial_risk) if initial_risk else 0.0

    mae_val = 0.0
    mfe_val = 0.0

    for step_idx, (_, row) in enumerate(future_candles.iterrows()):
        trade.duration_bars += 1
        open_p = float(row["open"])
        high_p = float(row["high"])
        low_p = float(row["low"])
        close_p = float(row["close"])
        bar_time = str(row["time"])

        # Atualiza MAE e MFE
        if is_buy:
            adverse = entry_price - low_p
            favorable = high_p - entry_price
        else:
            adverse = high_p - entry_price
            favorable = entry_price - low_p

        if adverse > mae_val:
            mae_val = adverse
        if favorable > mfe_val:
            mfe_val = favorable

        stop_hit = False
        stop_exit_price = 0.0
        donchian_hit = False
        donchian_exit_price = 0.0
        donchian_level = 0.0
        target_hit = False
        target_idx_hit = None

        # 1. Verifica Stop Loss com tratamento estrito de Gaps
        if stop_price is not None:
            if is_buy:
                if open_p <= stop_price:
                    stop_hit = True
                    stop_exit_price = open_p
                elif low_p <= stop_price:
                    stop_hit = True
                    stop_exit_price = stop_price
            else:
                if open_p >= stop_price:
                    stop_hit = True
                    stop_exit_price = open_p
                elif high_p >= stop_price:
                    stop_hit = True
                    stop_exit_price = stop_price

        # 2. Verifica Saída por Donchian Exit 20 se configurado na estratégia
        if exit_lookback and full_df is not None and entry_index is not None:
            global_k = entry_index + 1 + step_idx
            if global_k >= exit_lookback:
                prior_20 = full_df.iloc[global_k - exit_lookback : global_k]
                if is_buy:
                    donchian_level = float(prior_20["low"].min())
                    if open_p <= donchian_level:
                        donchian_hit = True
                        donchian_exit_price = open_p
                    elif low_p <= donchian_level:
                        donchian_hit = True
                        donchian_exit_price = donchian_level
                else:
                    donchian_level = float(prior_20["high"].max())
                    if open_p >= donchian_level:
                        donchian_hit = True
                        donchian_exit_price = open_p
                    elif high_p >= donchian_level:
                        donchian_hit = True
                        donchian_exit_price = donchian_level

        # 3. Verifica alvos fixos se existirem
        for t_idx, target in enumerate(targets):
            if is_buy and high_p >= target:
                target_hit = True
                target_idx_hit = t_idx
                break
            elif not is_buy and low_p <= target:
                target_hit = True
                target_idx_hit = t_idx
                break

        # Resolução de ambiguidade intrabar entre Stop Loss e Alvo fixo
        if stop_hit and target_hit:
            trade.intrabar_conflict_resolved = True
            effective_policy = policy
            if policy == IntrabarPolicy.CONSERVATIVE:
                effective_policy = IntrabarPolicy.STOP_FIRST
            elif policy == IntrabarPolicy.OPTIMISTIC:
                effective_policy = IntrabarPolicy.TARGET_FIRST

            if effective_policy == IntrabarPolicy.STOP_FIRST:
                target_hit = False
            elif effective_policy == IntrabarPolicy.TARGET_FIRST:
                stop_hit = False
            elif effective_policy == IntrabarPolicy.UNRESOLVED:
                trade.status = "UNRESOLVED"
                trade.exit_price = entry_price
                trade.exit_time = bar_time
                trade.mae = mae_val
                trade.mfe = mfe_val
                return trade

        # Resolução de ambiguidade intrabar entre Stop Loss e Donchian Exit
        if stop_hit and donchian_hit:
            trade.intrabar_conflict_resolved = True
            if is_buy:
                if donchian_level > stop_price:
                    trade.status = "WIN" if donchian_exit_price > entry_price else "LOSS"
                    trade.exit_price = donchian_exit_price
                    trade.exit_reason = "DONCHIAN_EXIT"
                else:
                    trade.status = "LOSS"
                    trade.exit_price = stop_exit_price
                    trade.exit_reason = "STOP"
            else:
                if donchian_level < stop_price:
                    trade.status = "WIN" if donchian_exit_price < entry_price else "LOSS"
                    trade.exit_price = donchian_exit_price
                    trade.exit_reason = "DONCHIAN_EXIT"
                else:
                    trade.status = "LOSS"
                    trade.exit_price = stop_exit_price
                    trade.exit_reason = "STOP"
            trade.exit_time = bar_time
            break

        if donchian_hit:
            trade.status = "WIN" if (donchian_exit_price > entry_price if is_buy else donchian_exit_price < entry_price) else "LOSS"
            trade.exit_price = donchian_exit_price
            trade.exit_time = bar_time
            trade.exit_reason = "DONCHIAN_EXIT"
            break

        if stop_hit:
            trade.status = "LOSS"
            trade.exit_price = stop_exit_price
            trade.exit_time = bar_time
            trade.exit_reason = "STOP"
            break

        if target_hit:
            trade.status = "WIN"
            trade.exit_price = targets[target_idx_hit] if target_idx_hit is not None else (high_p if is_buy else low_p)
            trade.exit_time = bar_time
            trade.hit_target_index = target_idx_hit
            trade.exit_reason = "TARGET"
            break

    # Se a simulação chegou ao fim do histórico disponível sem fechar
    if trade.status == "OPEN":
        trade.exit_price = float(future_candles["close"].iloc[-1])
        trade.exit_time = str(future_candles["time"].iloc[-1])
        trade.exit_reason = "END_OF_DATA"
        pnl = (trade.exit_price - entry_price) if is_buy else (entry_price - trade.exit_price)
        if abs(pnl) < 1e-6:
            trade.status = "BREAKEVEN"
        elif pnl > 0:
            trade.status = "WIN"
        else:
            trade.status = "LOSS"

    # Cálculo do resultado bruto e líquido
    if is_buy:
        raw_diff = trade.exit_price - entry_price
    else:
        raw_diff = entry_price - trade.exit_price

    trade.gross_profit = raw_diff

    # Dedução de custos (spread, comissão, swap)
    spread_cost = costs.spread_points * costs.point_value
    comm_cost = costs.commission_per_trade
    swap_cost = costs.swap_per_bar * trade.duration_bars

    trade.net_profit = raw_diff - spread_cost - comm_cost - swap_cost
    trade.mae = mae_val
    trade.mfe = mfe_val

    if trade.initial_risk > 0.0:
        trade.r_multiple_gross = trade.gross_profit / trade.initial_risk
        trade.r_multiple_net = trade.net_profit / trade.initial_risk
    else:
        trade.r_multiple_gross = 0.0
        trade.r_multiple_net = 0.0

    return trade
