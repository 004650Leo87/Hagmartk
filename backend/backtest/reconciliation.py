from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from backend.backtest.simulator import TradeSimulation


@dataclass
class BacktestReconciliationReport:
    """Relatório de reconciliação contábil automatizado para simulações do Strategy Lab."""

    trades_checked: int = 0
    trades_with_errors: int = 0
    sum_gross: float = 0.0
    sum_costs: float = 0.0
    sum_net: float = 0.0
    reported_net: float = 0.0
    net_difference: float = 0.0
    r_difference: float = 0.0
    pf_difference: float = 0.0
    expectancy_difference: float = 0.0
    drawdown_difference: float = 0.0
    passed: bool = False
    details: List[str] = field(default_factory=list)


def reconcile_backtest(trades: List[TradeSimulation], tolerance: float = 1e-4) -> BacktestReconciliationReport:
    """Valida minuciosamente a matemática contábil trade-a-trade e agregada de um experimento."""
    report = BacktestReconciliationReport()

    if not trades:
        report.passed = True
        return report

    report.trades_checked = len(trades)
    sum_gross = 0.0
    sum_costs = 0.0
    sum_net = 0.0
    errors_count = 0

    for t in trades:
        # Custo total debitado nesta operação: (slippage_points * point_value) + (spread_points * point_value) + commission + swap
        slippage_cost = t.costs.slippage_points * t.costs.point_value
        spread_cost = t.costs.spread_points * t.costs.point_value
        comm_cost = t.costs.commission_per_trade
        swap_cost = t.costs.swap_per_bar * t.duration_bars

        trade_costs = slippage_cost + spread_cost + comm_cost + swap_cost

        # Preço de referência original sem derrapagem
        is_buy = t.event.direction.value in ["BUY", "BULLISH"]
        ref_price = t.event.metadata.get("breakout_level", t.event.reference_price)
        if t.event.metadata.get("open_at_trigger") and is_buy and t.event.metadata["open_at_trigger"] > ref_price:
            ref_price = t.event.metadata["open_at_trigger"]
        elif t.event.metadata.get("open_at_trigger") and not is_buy and t.event.metadata["open_at_trigger"] < ref_price:
            ref_price = t.event.metadata["open_at_trigger"]

        true_gross_pnl = (t.exit_price - ref_price) if is_buy else (ref_price - t.exit_price)
        expected_net = true_gross_pnl - trade_costs

        if abs(t.net_profit - expected_net) > tolerance:
            errors_count += 1
            report.details.append(
                f"Erro no trade {t.trade_id}: net_profit={t.net_profit:.4f}, esperado={expected_net:.4f}"
            )

        sum_gross += true_gross_pnl
        sum_costs += trade_costs
        sum_net += t.net_profit

    report.trades_with_errors = errors_count
    report.sum_gross = float(sum_gross)
    report.sum_costs = float(sum_costs)
    report.sum_net = float(sum_net)
    report.reported_net = float(sum([t.net_profit for t in trades]))
    report.net_difference = float(abs(report.sum_net - (report.sum_gross - report.sum_costs)))

    report.passed = (errors_count == 0) and (report.net_difference <= tolerance)

    return report
