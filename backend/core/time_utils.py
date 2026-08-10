"""Helper centralizado de normalização temporal para o Projeto Hagmartk.

Garante que todos os timestamps (UTC, timezone-aware, timezone-naive,
strings ISO, pandas Timestamps e timestamps do MetaTrader 5) sejam
convertidos e comparados de forma padronizada em UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import pandas as pd


def parse_utc_timestamp(ts_input: Any) -> Optional[datetime]:
    """Converte qualquer formato de timestamp em um datetime UTC (timezone-aware).

    Suporta:
    - datetime (naive ou aware)
    - pd.Timestamp (naive ou aware)
    - string ISO 8601 (com 'T' ou espaço, com ou sem 'Z')
    - int/float (unix epoch em segundos)
    """
    if ts_input is None:
        return None

    if isinstance(ts_input, str):
        s = ts_input.strip()
        if not s:
            return None
        # Tentar pd.Timestamp para flexibilidade de parsing
        try:
            pdt = pd.Timestamp(s)
            if pdt.tzinfo is None:
                pdt = pdt.tz_localize("UTC")
            else:
                pdt = pdt.tz_convert("UTC")
            return pdt.to_pydatetime()
        except Exception:
            pass

        # Parse defensivo com strptime
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    if isinstance(ts_input, pd.Timestamp):
        if ts_input.tzinfo is None:
            pdt = ts_input.tz_localize("UTC")
        else:
            pdt = ts_input.tz_convert("UTC")
        return pdt.to_pydatetime()

    if isinstance(ts_input, datetime):
        if ts_input.tzinfo is None:
            return ts_input.replace(tzinfo=timezone.utc)
        return ts_input.astimezone(timezone.utc)

    if isinstance(ts_input, (int, float)):
        try:
            return datetime.fromtimestamp(ts_input, tz=timezone.utc)
        except Exception:
            return None

    return None


def now_utc_str() -> str:
    """Retorna o timestamp UTC atual formatado como string 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def now_utc_datetime() -> datetime:
    """Retorna o objeto datetime UTC atual (timezone-aware)."""
    return datetime.now(timezone.utc)


def format_utc_str(dt: datetime) -> str:
    """Formata datetime UTC como string padronizada 'YYYY-MM-DD HH:MM:SS'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
