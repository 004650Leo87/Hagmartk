from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from backend.backtest.simulator import TradeSimulation


@dataclass
class ConcentrationConfig:
    # Thresholds operacionais explícitos do Hagmartk para classificação de risco de concentração
    top_1_extreme_threshold_pct: float = 50.0   # Se o 1º melhor trade explica > 50% do lucro
    top_3_high_threshold_pct: float = 65.0      # Se os 3 melhores explicam > 65% do lucro
    top_5_moderate_threshold_pct: float = 75.0  # Se os 5 melhores explicam > 75% do lucro


@dataclass
class OutlierImpactMetrics:
    original_net_profit: float = 0.0
    original_mean_R: float = 0.0
    profit_without_best: float = 0.0
    mean_R_without_best: float = 0.0
    profit_without_top_3: float = 0.0
    mean_R_without_top_3: float = 0.0
    profit_without_top_5: float = 0.0
    mean_R_without_top_5: float = 0.0


@dataclass
class TemporalConcentrationReport:
    by_year: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_quarter: Dict[str, Dict[str, float]] = field(default_factory=dict)
    total_years: int = 0
    positive_years: int = 0
    negative_years: int = 0
    positive_period_ratio: float = 0.0


@dataclass
class ConcentrationReport:
    total_net_profit: float = 0.0
    best_trade_net: float = 0.0
    worst_trade_net: float = 0.0
    top_1_contribution_pct: float = 0.0
    top_3_contribution_pct: float = 0.0
    top_5_contribution_pct: float = 0.0
    top_10_pct_trades_contribution_pct: float = 0.0
    outliers: OutlierImpactMetrics = field(default_factory=OutlierImpactMetrics)
    temporal: TemporalConcentrationReport = field(default_factory=TemporalConcentrationReport)
    concentration_risk: str = "LOW"  # "LOW", "MODERATE", "HIGH", "EXTREME"
    risk_reasons: List[str] = field(default_factory=list)


def analyze_concentration_and_outliers(
    trades: List[TradeSimulation],
    config: Optional[ConcentrationConfig] = None,
) -> ConcentrationReport:
    """Audita a concentração de resultados por trades individuais e agrupamentos temporais."""
    cfg = config or ConcentrationConfig()
    report = ConcentrationReport()

    if not trades:
        return report

    net_pnls = [t.net_profit for t in trades]
    net_Rs = [t.r_multiple_net for t in trades]
    total_net = float(sum(net_pnls))
    report.total_net_profit = total_net

    sorted_trades = sorted(trades, key=lambda x: x.net_profit, reverse=True)
    report.best_trade_net = float(sorted_trades[0].net_profit)
    report.worst_trade_net = float(sorted_trades[-1].net_profit)

    # Cálculo da contribuição percentual dos N melhores trades
    if total_net > 0:
        top_1_net = float(sorted_trades[0].net_profit)
        top_3_net = float(sum(t.net_profit for t in sorted_trades[:3]))
        top_5_net = float(sum(t.net_profit for t in sorted_trades[:5]))

        k_10pct = max(1, int(len(sorted_trades) * 0.10))
        top_10pct_net = float(sum(t.net_profit for t in sorted_trades[:k_10pct]))

        report.top_1_contribution_pct = float((top_1_net / total_net) * 100.0)
        report.top_3_contribution_pct = float((top_3_net / total_net) * 100.0)
        report.top_5_contribution_pct = float((top_5_net / total_net) * 100.0)
        report.top_10_pct_trades_contribution_pct = float((top_10pct_net / total_net) * 100.0)

    # Impacto da remoção de Outliers
    orig_mean_R = float(np.mean(net_Rs))

    without_best_pnls = [t.net_profit for t in sorted_trades[1:]]
    without_best_Rs = [t.r_multiple_net for t in sorted_trades[1:]]

    without_top_3_pnls = [t.net_profit for t in sorted_trades[3:]]
    without_top_3_Rs = [t.r_multiple_net for t in sorted_trades[3:]]

    without_top_5_pnls = [t.net_profit for t in sorted_trades[5:]]
    without_top_5_Rs = [t.r_multiple_net for t in sorted_trades[5:]]

    report.outliers = OutlierImpactMetrics(
        original_net_profit=total_net,
        original_mean_R=orig_mean_R,
        profit_without_best=float(sum(without_best_pnls)),
        mean_R_without_best=float(np.mean(without_best_Rs)) if without_best_Rs else 0.0,
        profit_without_top_3=float(sum(without_top_3_pnls)),
        mean_R_without_top_3=float(np.mean(without_top_3_Rs)) if without_top_3_Rs else 0.0,
        profit_without_top_5=float(sum(without_top_5_pnls)),
        mean_R_without_top_5=float(np.mean(without_top_5_Rs)) if without_top_5_Rs else 0.0,
    )

    # Concentração Temporal (Por Ano e Por Trimestre)
    records = []
    for t in trades:
        date_str = t.entry_time[:10]
        year = date_str[:4]
        try:
            month = int(date_str[5:7])
            q = (month - 1) // 3 + 1
            quarter = f"{year}-Q{q}"
        except Exception:
            quarter = f"{year}-Q1"
        records.append({"year": year, "quarter": quarter, "net_profit": t.net_profit, "net_R": t.r_multiple_net})

    tdf = pd.DataFrame(records)
    by_yr = {}
    pos_years = 0
    neg_years = 0

    if not tdf.empty:
        for y, group in tdf.groupby("year"):
            y_net = float(group["net_profit"].sum())
            y_cnt = len(group)
            by_yr[str(y)] = {"trades": y_cnt, "net_profit": y_net, "mean_R": float(group["net_R"].mean())}
            if y_net > 0:
                pos_years += 1
            elif y_net < 0:
                neg_years += 1

        by_q = {}
        for q, group in tdf.groupby("quarter"):
            by_q[str(q)] = {"trades": len(group), "net_profit": float(group["net_profit"].sum())}

        tot_y = len(by_yr)
        report.temporal = TemporalConcentrationReport(
            by_year=by_yr,
            by_quarter=by_q,
            total_years=tot_y,
            positive_years=pos_years,
            negative_years=neg_years,
            positive_period_ratio=(pos_years / tot_y) if tot_y > 0 else 0.0,
        )

    # Classificação do Risco de Concentração
    reasons = []
    if report.top_1_contribution_pct >= cfg.top_1_extreme_threshold_pct:
        report.concentration_risk = "EXTREME"
        reasons.append(f"O 1º melhor trade representa {report.top_1_contribution_pct:.1f}% do lucro total (>= {cfg.top_1_extreme_threshold_pct}%).")
    elif report.top_3_contribution_pct >= cfg.top_3_high_threshold_pct:
        report.concentration_risk = "HIGH"
        reasons.append(f"Os 3 melhores trades representam {report.top_3_contribution_pct:.1f}% do lucro total (>= {cfg.top_3_high_threshold_pct}%).")
    elif report.top_5_contribution_pct >= cfg.top_5_moderate_threshold_pct:
        report.concentration_risk = "MODERATE"
        reasons.append(f"Os 5 melhores trades representam {report.top_5_contribution_pct:.1f}% do lucro total (>= {cfg.top_5_moderate_threshold_pct}%).")
    else:
        report.concentration_risk = "LOW"
        reasons.append("Lucro razoavelmente distribuído entre os trades vencedores.")

    if report.outliers.profit_without_top_3 <= 0 and total_net > 0:
        if report.concentration_risk != "EXTREME":
            report.concentration_risk = "HIGH"
        reasons.append("Remover os 3 melhores trades torna o resultado líquido total negativo ou nulo.")

    report.risk_reasons = reasons
    return report
