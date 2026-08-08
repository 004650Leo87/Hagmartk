from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.domain.events import Direction, StrategyEvent
from backend.strategies.base import BaseStrategy


@dataclass
class FactorCombinationConfig:
    """Configuração da combinação de fatores a serem testados isoladamente ou em confluência."""

    name: str
    use_dvap: bool = False
    use_volume: bool = False
    use_didi: bool = False
    use_trix: bool = False
    use_adx: bool = False


class FactorPipelineStrategy(BaseStrategy):
    """Arquitetura modular de pesquisa de fatores e confluências (DVAP / Didi / Volume / TRIX / ADX)."""

    def __init__(self, factor_config: Optional[FactorCombinationConfig] = None) -> None:
        cfg = factor_config or FactorCombinationConfig(name="DVAP_PURA", use_dvap=True)
        self.factor_config = cfg

        self.strategy_id = f"factor_pipeline_{cfg.name.lower()}"
        self.name = f"Factor Pipeline — {cfg.name}"
        self.version = "1.0.0"
        self.description = f"Pipeline de testes de fatores quantitativos: {cfg.name}"
        self.allowed_timeframes = ["M15", "H1", "H4", "D1"]
        self.max_concurrent_positions_per_symbol = 1
        self.minimum_required_bars = 50
        self.warmup_bars = 80

        self.parameters: Dict[str, Any] = {
            "use_dvap": cfg.use_dvap,
            "use_volume": cfg.use_volume,
            "use_didi": cfg.use_didi,
            "use_trix": cfg.use_trix,
            "use_adx": cfg.use_adx,
        }

    def evaluate(
        self,
        history: pd.DataFrame,
        symbol: str,
        timeframe: str,
        is_closed_bar: bool = True,
    ) -> List[StrategyEvent]:
        """Avalia a confluência dos fatores ativados na configuração.

        Nota: Esta é a estrutura arquitetural. As fórmulas definitivas da DVAP serão especificadas
        e integradas na fase subsequente após validação dos pivôs e divergências.
        """
        if history is None or len(history) < self.minimum_required_bars:
            return []

        # Exemplo arquitetural de avaliação de confluência
        last_row = history.iloc[-1]
        time_t = str(last_row["time"])
        price_t = float(last_row["close"])

        # Placeholder arquitetural para disparos de teste de fatores
        return []


def analyze_didi_confirmation_impact(
    events_unconfirmed: List[Dict[str, Any]],
    events_confirmed: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Calcula estatísticas de impacto da confirmação Didi Index sobre os sinais base."""
    n_unconf = len(events_unconfirmed)
    n_conf = len(events_confirmed)

    if n_unconf == 0:
        return {
            "total_unconfirmed": 0,
            "total_confirmed": 0,
            "confirmation_rate_pct": 0.0,
            "average_lag_bars": 0.0,
            "median_lag_bars": 0.0,
            "mfe_lost_waiting_confirmation": 0.0,
            "mae_avoided_waiting_confirmation": 0.0,
        }

    conf_rate = (n_conf / n_unconf) * 100.0
    lags = [e.get("lag_bars", 0) for e in events_confirmed]

    return {
        "total_unconfirmed": n_unconf,
        "total_confirmed": n_conf,
        "confirmation_rate_pct": round(conf_rate, 2),
        "average_lag_bars": round(float(np.mean(lags)), 2) if lags else 0.0,
        "median_lag_bars": round(float(np.median(lags)), 2) if lags else 0.0,
        "mfe_lost_waiting_confirmation": 0.0,
        "mae_avoided_waiting_confirmation": 0.0,
    }
