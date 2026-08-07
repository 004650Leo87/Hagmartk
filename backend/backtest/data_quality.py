from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass
class DataQualityReport:
    is_valid: bool
    status: str  # "VALID", "INVALID_DATA", "INSUFFICIENT_HISTORY"
    total_candles: int
    missing_values_count: int = 0
    duplicate_timestamps_count: int = 0
    chronological_violations_count: int = 0
    invalid_ohlc_count: int = 0
    reasons: List[str] = field(default_factory=list)


def validate_data_quality(
    df: pd.DataFrame,
    warmup_bars: int = 20,
    min_eval_bars: int = 10,
) -> DataQualityReport:
    """Valida a integridade estatística dos candles antes de executar um backtest."""
    reasons: List[str] = []

    if df is None or df.empty:
        return DataQualityReport(
            is_valid=False,
            status="INSUFFICIENT_HISTORY",
            total_candles=0,
            reasons=["Histórico de candles vazio ou ausente"],
        )

    total_candles = len(df)
    min_required = warmup_bars + min_eval_bars

    if total_candles < min_required:
        return DataQualityReport(
            is_valid=False,
            status="INSUFFICIENT_HISTORY",
            total_candles=total_candles,
            reasons=[
                f"Histórico insuficiente ({total_candles} candles). "
                f"Necessário no mínimo {min_required} (warmup={warmup_bars} + eval={min_eval_bars})"
            ],
        )

    # 1. Colunas obrigatórias
    required_cols = {"time", "open", "high", "low", "close"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        return DataQualityReport(
            is_valid=False,
            status="INVALID_DATA",
            total_candles=total_candles,
            reasons=[f"Colunas obrigatórias ausentes no DataFrame: {missing_cols}"],
        )

    # 2. Valores nulos
    missing_values = df[["open", "high", "low", "close"]].isna().sum().sum()
    if missing_values > 0:
        reasons.append(f"Encontrados {missing_values} valores nulos/NaN em preços OHLC")

    # 3. Timestamps duplicados
    duplicates = df["time"].duplicated().sum()
    if duplicates > 0:
        reasons.append(f"Encontrados {duplicates} timestamps duplicados")

    # 4. Ordem cronológica
    times = pd.to_datetime(df["time"])
    chronological_violations = (times.diff().dt.total_seconds() < 0).sum()
    if chronological_violations > 0:
        reasons.append(f"Encontradas {chronological_violations} violações de ordem cronológica")

    # 5. OHLC inválido (low > high ou open/close fora da faixa [low, high])
    invalid_ohlc = (
        (df["low"] > df["high"])
        | (df["open"] < df["low"])
        | (df["open"] > df["high"])
        | (df["close"] < df["low"])
        | (df["close"] > df["high"])
    ).sum()

    if invalid_ohlc > 0:
        reasons.append(f"Encontrados {invalid_ohlc} candles com relação OHLC inconsistente")

    is_valid = bool(
        missing_values == 0
        and duplicates == 0
        and chronological_violations == 0
        and invalid_ohlc == 0
    )

    status = "VALID" if is_valid else "INVALID_DATA"

    return DataQualityReport(
        is_valid=is_valid,
        status=status,
        total_candles=total_candles,
        missing_values_count=int(missing_values),
        duplicate_timestamps_count=int(duplicates),
        chronological_violations_count=int(chronological_violations),
        invalid_ohlc_count=int(invalid_ohlc),
        reasons=reasons,
    )
