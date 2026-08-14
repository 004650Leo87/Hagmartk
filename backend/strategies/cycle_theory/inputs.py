"""
CYCLE THEORY V111 — FIDELITY PORT
Inputs — cópia 1:1 dos 30 parâmetros de entrada + 4 constantes internas do MQ5.

Contagem confirmada diretamente no arquivo original (linhas 89-135):
  GESTÃO DE CAPITAL      -> 4  (InpLotMode, InpFixedLot, InpBalanceStep, InpMagicNum)
  PARCIAIS               -> 2  (InpUsePartial, InpPartialPct)
  BLINDAGEM DA CONTA     -> 4  (InpMaxDailyLoss, InpMaxDailyProfit, InpMaxDailyTrades, InpMaxSpread)
  PROTEÇÃO DE LUCRO      -> 3  (InpUseCapitalTrail, InpCapitalGoal, InpCapitalProtect)
  MODO SPLIT             -> 1  (InpSplitChannelPoints)
  HORÁRIO                -> 3  (InpStartTime, InpEndEntryTime, InpCloseAllTime)
  ESTRATÉGIA              -> 6  (InpTriggerMode, InpFixedTF, InpEntryMode, InpMaxChannelSize,
                                  InpStopBuffer, InpExpansionLevels)
  GESTÃO DA ORDEM        -> 4  (InpUseBreakeven, InpBE_Activation, InpSendPush, InpDeviation)
  TRAILING STOP          -> 3  (InpTrailingMode, InpATR_Period, InpATR_Multiplier)
  TOTAL                  -> 30

Constantes internas (não são inputs, são `const`/`#define` no original) -> 4:
  LICENSE_ACCOUNT_1, LICENSE_ACCOUNT_2, LICENSE_LIMIT, BE_PROTECT_PTS

NENHUM default foi alterado em relação ao MQ5.
"""
from dataclasses import dataclass
from datetime import date

from .enums import LotMode, EntryMode, TrailingMode, TriggerMode

TOTAL_INPUTS = 30
TOTAL_CONSTANTS = 4

# ---- Constantes internas (não configuráveis pelo usuário no original) ----
LICENSE_ACCOUNT_1: int = 0
LICENSE_ACCOUNT_2: int = 0
LICENSE_LIMIT: date = date(2050, 12, 31)
BE_PROTECT_PTS: int = 10


@dataclass
class CycleTheoryInputs:
    # === GESTÃO DE CAPITAL ===
    lot_mode: LotMode = LotMode.LOT_AUTO_BALANCE
    fixed_lot: float = 0.01
    balance_step: float = 500.0
    magic_num: int = 1

    # === PARCIAIS (SCALE-OUT) ===
    use_partial: bool = True
    partial_pct: float = 50.0

    # === BLINDAGEM DA CONTA ===
    max_daily_loss: float = 0.0
    max_daily_profit: float = 0.0
    max_daily_trades: int = 0
    max_spread: int = 30

    # === PROTEÇÃO DE LUCRO DO DIA ===
    use_capital_trail: bool = True
    capital_goal: float = 50.0
    capital_protect: float = 25.0

    # === MODO SPLIT ===
    split_channel_points: int = 1000

    # === HORÁRIO ===
    start_time: str = "01:00"
    end_entry_time: str = "23:00"
    close_all_time: str = "23:50"

    # === ESTRATÉGIA ===
    trigger_mode: TriggerMode = TriggerMode.GATILHO_EXPANSAO
    fixed_tf: str = "PERIOD_CURRENT"  # equivalente a ENUM_TIMEFRAMES InpFixedTF
    entry_mode: EntryMode = EntryMode.ENTRY_PULLBACK_25
    max_channel_size: int = 3000
    stop_buffer: int = 20
    expansion_levels: int = 3

    # === GESTÃO DA ORDEM ===
    use_breakeven: bool = False
    be_activation: int = 500
    send_push: bool = False
    deviation: int = 100

    # === TRAILING STOP ===
    trailing_mode: TrailingMode = TrailingMode.TRAIL_ATR
    atr_period: int = 14
    atr_multiplier: float = 1.5

    def field_count(self) -> int:
        return len(self.__dataclass_fields__)


def baseline_inputs() -> CycleTheoryInputs:
    """Baseline de paridade — EXATAMENTE os defaults do MQ5 (Seção 68 do prompt-mestre)."""
    return CycleTheoryInputs()
