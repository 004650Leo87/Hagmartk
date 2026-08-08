from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass
class EventStudyRecord:
    """Registro estruturado de sequência temporal de eventos para estudo de confluências e transição de estados."""

    # Rastreabilidade temporal rigorosa contra Lookahead Bias
    observation_time: str
    pivot_time: Optional[str] = None
    confirmed_at: str = ""
    signal_at: str = ""
    entry_at: str = ""
    data_available_at_decision: str = ""

    # Eventos base e secundários (ex: divergência -> confirmação Didi)
    base_event_name: str = ""
    base_event_time: str = ""
    secondary_event_name: Optional[str] = None
    secondary_event_time: Optional[str] = None
    bars_to_secondary_event: Optional[int] = None

    # Preços e métricas de excursão adversa / favorável
    price_at_base_event: float = 0.0
    price_at_confirmation: float = 0.0
    mfe_before_confirmation: float = 0.0
    mae_before_confirmation: float = 0.0
    mfe_after_confirmation: float = 0.0
    mae_after_confirmation: float = 0.0

    # Variáveis de contexto (volume, tendência, volatilidade)
    context_features: Dict[str, Any] = field(default_factory=dict)
    outcome: Dict[str, Any] = field(default_factory=dict)


class EventStudyEngine:
    """Motor de análise de sequências temporais de eventos e impacto de confirmações."""

    @staticmethod
    def analyze_event_sequence(
        df: pd.DataFrame,
        base_events: List[Dict[str, Any]],
        confirmation_evaluator_fn: Optional[Any] = None,
        forward_bars: int = 20,
    ) -> List[EventStudyRecord]:
        records = []
        if df is None or df.empty or not base_events:
            return records

        time_to_idx = {str(t): i for i, t in enumerate(df["time"])}

        for evt in base_events:
            base_time = evt.get("time")
            if base_time not in time_to_idx:
                continue

            base_idx = time_to_idx[base_time]
            price_base = float(evt.get("price", df["close"].iloc[base_idx]))

            rec = EventStudyRecord(
                observation_time=base_time,
                pivot_time=evt.get("pivot_time"),
                confirmed_at=base_time,
                signal_at=base_time,
                entry_at=base_time,
                data_available_at_decision=base_time,
                base_event_name=evt.get("name", "BASE_EVENT"),
                base_event_time=base_time,
                price_at_base_event=price_base,
            )

            # Avaliação de confirmação secundária (ex: Didi Index)
            conf_idx = None
            if confirmation_evaluator_fn is not None:
                for k in range(base_idx + 1, min(len(df), base_idx + forward_bars + 1)):
                    sub_df = df.iloc[: k + 1]  # Sem lookahead
                    if confirmation_evaluator_fn(sub_df, evt):
                        conf_idx = k
                        rec.secondary_event_name = "CONFIRMATION_EVENT"
                        rec.secondary_event_time = str(df["time"].iloc[k])
                        rec.confirmed_at = str(df["time"].iloc[k])
                        rec.bars_to_secondary_event = k - base_idx
                        rec.price_at_confirmation = float(df["close"].iloc[k])
                        break

            # Cálculo de MFE/MAE antes e depois da confirmação
            highs = df["high"].values
            lows = df["low"].values
            closes = df["close"].values

            end_idx = min(len(df) - 1, base_idx + forward_bars)

            if conf_idx is not None:
                # Excursão antes da confirmação
                sub_h_pre = highs[base_idx : conf_idx + 1]
                sub_l_pre = lows[base_idx : conf_idx + 1]
                rec.mfe_before_confirmation = float(np.max(sub_h_pre) - price_base)
                rec.mae_before_confirmation = float(price_base - np.min(sub_l_pre))

                # Excursão após confirmação
                sub_h_post = highs[conf_idx : end_idx + 1]
                sub_l_post = lows[conf_idx : end_idx + 1]
                rec.mfe_after_confirmation = float(np.max(sub_h_post) - rec.price_at_confirmation)
                rec.mae_after_confirmation = float(rec.price_at_confirmation - np.min(sub_l_post))
            else:
                sub_h = highs[base_idx : end_idx + 1]
                sub_l = lows[base_idx : end_idx + 1]
                rec.mfe_before_confirmation = float(np.max(sub_h) - price_base)
                rec.mae_before_confirmation = float(price_base - np.min(sub_l))

            records.append(rec)

        return records
