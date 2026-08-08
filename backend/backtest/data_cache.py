from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from typing import Any, Dict, Optional
import pandas as pd


@dataclass
class DatasetMetadata:
    source_broker: str
    symbol: str
    timeframe: str
    start_timestamp: str
    end_timestamp: str
    candle_count: int
    dataset_hash: str
    created_at: str


class OHLCDataCache:
    """Gerenciador de cache local de dados OHLC com identificação inequívoca por Hash SHA-256."""

    def __init__(self, cache_dir: str = "data_cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    @staticmethod
    def compute_dataset_hash(df: pd.DataFrame) -> str:
        """Calcula o hash SHA-256 canônico da série OHLC bruta."""
        if df is None or df.empty:
            return ""
        # Usa colunas essenciais ordenadas
        cols = ["time", "open", "high", "low", "close", "tick_volume"]
        sub = df[[c for c in cols if c in df.columns]]
        raw_bytes = sub.to_csv(index=False).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()

    def get_cache_paths(self, symbol: str, timeframe: str) -> tuple[str, str]:
        base_name = f"{symbol}_{timeframe}"
        data_path = os.path.join(self.cache_dir, f"{base_name}.csv")
        meta_path = os.path.join(self.cache_dir, f"{base_name}_meta.json")
        return data_path, meta_path

    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        source_broker: str = "Pepperstone_MT5",
    ) -> DatasetMetadata:
        """Salva a série OHLC bruta e seus metadados no cache local."""
        data_path, meta_path = self.get_cache_paths(symbol, timeframe)

        dataset_hash = self.compute_dataset_hash(df)
        t_start = str(df["time"].iloc[0])
        t_end = str(df["time"].iloc[-1])
        cnt = len(df)

        meta = DatasetMetadata(
            source_broker=source_broker,
            symbol=symbol,
            timeframe=timeframe,
            start_timestamp=t_start,
            end_timestamp=t_end,
            candle_count=cnt,
            dataset_hash=dataset_hash,
            created_at=pd.Timestamp.now(tz="UTC").isoformat(),
        )

        df.to_csv(data_path, index=False)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta.__dict__, f, indent=2)

        return meta

    def load(
        self,
        symbol: str,
        timeframe: str,
        expected_hash: Optional[str] = None,
    ) -> tuple[Optional[pd.DataFrame], Optional[DatasetMetadata]]:
        """Carrega dados OHLC do cache verificando a integridade dos metadados e o hash."""
        data_path, meta_path = self.get_cache_paths(symbol, timeframe)
        if not os.path.exists(data_path) or not os.path.exists(meta_path):
            return None, None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_dict = json.load(f)
            meta = DatasetMetadata(**meta_dict)

            df = pd.read_csv(data_path)
            actual_hash = self.compute_dataset_hash(df)

            if actual_hash != meta.dataset_hash:
                # Corrupção detectada
                return None, None

            if expected_hash and actual_hash != expected_hash:
                # Hash incompatível
                return None, None

            return df, meta
        except Exception:
            return None, None

