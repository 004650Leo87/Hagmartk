"""
CYCLE THEORY V111 — FIDELITY PORT
CycleTheoryPersistence — equivalente a SaveMemory()/LoadMemory() (linhas 237-265).

IMPORTANTE (Seção 47 da Source Audit): o original persiste EXATAMENTE:
  chHigh, chLow, expLevel, superSize, setupDir, refTimeStart, isSplitActive
Nada além disso. NÃO adicionar outros campos aqui silenciosamente.

Chaves nomeadas por Magic+Symbol (isolado por símbolo NESTE ponto específico,
ao contrário de várias outras funções documentadas como quirk na Source Audit).
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .state_machine import CycleTheoryStateMachine


@dataclass
class PersistedFields:
    ch_high: float
    ch_low: float
    exp_level: float
    super_size: float
    setup_dir: int
    ref_time_start: Optional[datetime]
    is_split_active: bool


class CycleTheoryPersistence:
    """Store em memória equivalente ao GlobalVariable do MT5 — em produção,
    o backend real (Postgres/etc.) substitui este dicionário por linha
    persistente, mas o CONTRATO de quais campos são salvos não muda."""

    def __init__(self) -> None:
        self._store: dict[str, PersistedFields] = {}

    @staticmethod
    def _key(magic: int, symbol: str) -> str:
        return f"{magic}:{symbol}"

    def save_memory(self, sm: CycleTheoryStateMachine) -> None:
        s = sm.state
        self._store[self._key(sm.magic, sm.symbol)] = PersistedFields(
            ch_high=s.ch_high,
            ch_low=s.ch_low,
            exp_level=s.exp_level,
            super_size=s.super_size,
            setup_dir=s.setup_dir,
            ref_time_start=s.ref_time_start,
            is_split_active=s.is_split_active,
        )

    def load_memory(self, sm: CycleTheoryStateMachine) -> bool:
        key = self._key(sm.magic, sm.symbol)
        if key not in self._store:
            return False
        f = self._store[key]
        s = sm.state
        s.ch_high = f.ch_high
        s.ch_low = f.ch_low
        s.exp_level = f.exp_level
        s.super_size = f.super_size
        s.setup_dir = f.setup_dir
        s.ref_time_start = f.ref_time_start
        s.channel_height = s.ch_high - s.ch_low
        s.is_split_active = f.is_split_active
        if s.is_split_active:
            s.mid_line50 = (s.ch_high + s.ch_low) / 2.0
        return True
