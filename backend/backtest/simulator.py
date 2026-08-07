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


def simulate_trade_outcome(
    event: StrategyEvent,
    future_candles: pd.DataFrame,
    costs: CostsConfig,
    policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE,
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

    if future_candles.empty:
        trade.status = "OPEN"
        return trade

    direction = event.direction
    entry_price = event.reference_price
    if event.entry_zone and len(event.entry_zone) == 2:
        # Se zona de entrada definida, usa o preço médio
        entry_price = (event.entry_zone[0] + event.entry_zone[1]) / 2.0

    stop_price = event.invalidation
    targets = event.targets or []

    # Ajuste de entrada por derrapagem (slippage)
    slippage_offset = costs.slippage_points * costs.point_value
    if direction == Direction.BUY:
        entry_price += slippage_offset
    else:
        entry_price -= slippage_offset

    trade.entry_price = entry_price
    trade.entry_time = str(future_candles["time"].iloc[0])

    mae_val = 0.0
    mfe_val = 0.0

    for idx, row in future_candles.iterrows():
        trade.duration_bars += 1
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        bar_time = str(row["time"])

        # Atualiza MAE e MFE
        if direction == Direction.BUY:
            adverse = entry_price - low
            favorable = high - entry_price
        else:
            adverse = high - entry_price
            favorable = entry_price - low

        if adverse > mae_val:
            mae_val = adverse
        if favorable > mfe_val:
            mfe_val = favorable

        # Verifica se Stop Loss e Alvo foram atingidos nesta barra
        stop_hit = False
        target_hit = False
        target_idx_hit = None

        if stop_price is not None:
            if direction == Direction.BUY and low <= stop_price:
                stop_hit = True
            elif direction == Direction.SELL and high >= stop_price:
                stop_hit = True

        for t_idx, target in enumerate(targets):
            if direction == Direction.BUY and high >= target:
                target_hit = True
                target_idx_hit = t_idx
                break
            elif direction == Direction.SELL and low <= target:
                target_hit = True
                target_idx_hit = t_idx
                break

        # Ambiguidade intrabar (Stop e Alvo tocados na mesma barra)
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

        # Trata encerramento por Stop Loss
        if stop_hit:
            trade.status = "LOSS"
            trade.exit_price = stop_price if stop_price is not None else low
            trade.exit_time = bar_time
            break

        # Trata encerramento por Alvo
        if target_hit:
            trade.status = "WIN"
            trade.exit_price = targets[target_idx_hit] if target_idx_hit is not None else high
            trade.exit_time = bar_time
            trade.hit_target_index = target_idx_hit
            break

    # Se a simulação terminou e a operação continuou aberta, usa o último preço de fechamento
    if trade.status == "OPEN":
        trade.exit_price = float(future_candles["close"].iloc[-1])
        trade.exit_time = str(future_candles["time"].iloc[-1])
        pnl = (trade.exit_price - entry_price) if direction == Direction.BUY else (entry_price - trade.exit_price)
        if abs(pnl) < 1e-6:
            trade.status = "BREAKEVEN"
        elif pnl > 0:
            trade.status = "WIN"
        else:
            trade.status = "LOSS"

    # Cálculo do resultado bruto e líquido
    if direction == Direction.BUY:
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

    return trade
