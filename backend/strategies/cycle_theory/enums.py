"""
CYCLE THEORY V111 — FIDELITY PORT
Enums — cópia semântica 1:1 dos enums do TEORIA_DOS_CICLOS_ULTIMATE_1.mq5 (v111.00)

REGRA: nenhuma alteração de significado ou de conjunto de valores.
"""
from enum import Enum, auto


class LotMode(Enum):
    LOT_FIXED = auto()
    LOT_AUTO_BALANCE = auto()


class EntryMode(Enum):
    ENTRY_MARKET = auto()
    ENTRY_PULLBACK_0 = auto()
    ENTRY_PULLBACK_25 = auto()
    ENTRY_PULLBACK_50 = auto()


class TrailingMode(Enum):
    TRAIL_OFF = auto()
    TRAIL_DYNAMIC = auto()
    TRAIL_STRUCTURAL = auto()
    TRAIL_ATR = auto()


class TriggerMode(Enum):
    """GATILHO_EXPANSAO e GATILHO_ZONA_NEUTRA são os dois modos do enum de gatilho
    (ENUM_MODO_GATILHO no original). SPLIT NÃO é um valor deste enum — é uma
    condição/modo estrutural derivada do tamanho do canal (isSplitActive),
    que pode coexistir com qualquer um dos dois modos de gatilho."""
    GATILHO_EXPANSAO = auto()
    GATILHO_ZONA_NEUTRA = auto()


class BotState(Enum):
    STATE_OFF = auto()
    STATE_STARTING = auto()
    STATE_COUNTING = auto()
    STATE_MONITORING = auto()
    STATE_TRADING = auto()


class PositionType(Enum):
    """Equivalente a POSITION_TYPE_BUY / POSITION_TYPE_SELL do MQ5."""
    BUY = auto()
    SELL = auto()


class OrderType(Enum):
    """Equivalente aos tipos de ordem pendente usados pelo EA."""
    BUY_LIMIT = auto()
    SELL_LIMIT = auto()
