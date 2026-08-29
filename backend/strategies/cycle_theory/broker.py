"""
CYCLE THEORY V111 — FIDELITY PORT
Camada de abstração de broker/mercado (equivalente às chamadas MQL5: SymbolInfo,
CTrade, PositionGetX, OrderGetX, HistoryDealGetX, iHigh/iLow/iClose/iTime/
iBarShift/iHighest/iLowest, CopyBuffer do ATR, etc.)

Esta camada NÃO faz parte da lógica estratégica — é a "ponte" que qualquer
motor real (MetaTrader5 python package, replay histórico, ou research/backtest)
deve implementar. Para os testes de fidelidade, usamos MockBroker, que é
determinístico e não depende de rede/MT5 real (indisponível neste ambiente).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import itertools

from .enums import PositionType, OrderType


@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass
class Position:
    ticket: int
    symbol: str
    magic: int
    type: PositionType
    volume: float
    price_open: float
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0
    swap: float = 0.0


@dataclass
class PendingOrder:
    ticket: int
    symbol: str
    magic: int
    type: OrderType
    volume: float
    price_open: float
    sl: float = 0.0
    tp: float = 0.0


@dataclass
class Deal:
    """Equivalente a um HistoryDeal do MT5."""
    ticket: int
    symbol: str
    magic: int
    entry: str  # "IN" | "OUT" | "OUT_BY"  (equivalente a DEAL_ENTRY_*)
    position_id: int
    profit: float
    swap: float
    commission: float
    time: datetime


class MockBroker:
    """
    Broker determinístico para testes unitários de fidelidade.

    Reproduz DELIBERADAMENTE os quirks de escopo do MQ5 original documentados
    na Source Audit (OBS-01): a maioria das funções de agregação filtra
    SOMENTE por magic, sem checar símbolo — EXCETO get_position_by_magic_symbol
    (equivalente a GetBotTicket), que filtra por magic + símbolo.
    """

    def __init__(self, symbol: str, point: float = 0.0001, digits: int = 4,
                 stops_level_pts: int = 0, freeze_level_pts: int = 0,
                 volume_step: float = 0.01, volume_min: float = 0.01,
                 volume_max: float = 100.0):
        self.symbol = symbol
        self.point = point
        self.digits = digits
        self.stops_level_pts = stops_level_pts
        self.freeze_level_pts = freeze_level_pts
        self.volume_step = volume_step
        self.volume_min = volume_min
        self.volume_max = volume_max

        self.bid: float = 0.0
        self.ask: float = 0.0
        self.spread_pts: int = 0

        self.balance: float = 100_000.0
        self.margin_free: float = 100_000.0
        self.margin_calculator = None

        self.now: datetime = datetime(2026, 1, 5, 1, 0, 0)  # broker server time

        self.bars: dict[str, list[Candle]] = {}  # keyed by timeframe string
        self.positions: list[Position] = []
        self.pending_orders: list[PendingOrder] = []
        self.deals: list[Deal] = []

        self._ticket_seq = itertools.count(1)
        self.atr_value: float = 0.0

        # instrumenta falhas forçadas para testes de "ERRO: retcode"
        self.force_trade_failure: bool = False

    def order_calc_margin_buy(self, lot: float):
        if self.margin_calculator is None:
            return None
        return float(self.margin_calculator(lot, self.ask))

    # ---------------- ordens/execução ----------------
    def next_ticket(self) -> int:
        return next(self._ticket_seq)

    def buy(self, lot: float, sl: float, tp: float, magic: int) -> Optional[int]:
        if self.force_trade_failure:
            return None
        tk = self.next_ticket()
        self.positions.append(Position(tk, self.symbol, magic, PositionType.BUY,
                                        lot, self.ask, sl, tp))
        self.deals.append(Deal(self.next_ticket(), self.symbol, magic, "IN", tk,
                                0.0, 0.0, 0.0, self.now))
        return tk

    def sell(self, lot: float, sl: float, tp: float, magic: int) -> Optional[int]:
        if self.force_trade_failure:
            return None
        tk = self.next_ticket()
        self.positions.append(Position(tk, self.symbol, magic, PositionType.SELL,
                                        lot, self.bid, sl, tp))
        self.deals.append(Deal(self.next_ticket(), self.symbol, magic, "IN", tk,
                                0.0, 0.0, 0.0, self.now))
        return tk

    def buy_limit(self, lot: float, price: float, sl: float, tp: float, magic: int) -> Optional[int]:
        if self.force_trade_failure:
            return None
        tk = self.next_ticket()
        self.pending_orders.append(PendingOrder(tk, self.symbol, magic, OrderType.BUY_LIMIT,
                                                  lot, price, sl, tp))
        return tk

    def sell_limit(self, lot: float, price: float, sl: float, tp: float, magic: int) -> Optional[int]:
        if self.force_trade_failure:
            return None
        tk = self.next_ticket()
        self.pending_orders.append(PendingOrder(tk, self.symbol, magic, OrderType.SELL_LIMIT,
                                                  lot, price, sl, tp))
        return tk

    def order_delete(self, ticket: int) -> bool:
        before = len(self.pending_orders)
        self.pending_orders = [o for o in self.pending_orders if o.ticket != ticket]
        return len(self.pending_orders) < before

    def position_modify(self, ticket: int, sl: float, tp: float) -> bool:
        for p in self.positions:
            if p.ticket == ticket:
                p.sl, p.tp = sl, tp
                return True
        return False

    def position_close(self, ticket: int, profit: float = 0.0) -> bool:
        for p in self.positions:
            if p.ticket == ticket:
                self.deals.append(Deal(self.next_ticket(), p.symbol, p.magic, "OUT",
                                        p.ticket, profit, 0.0, 0.0, self.now))
                self.positions.remove(p)
                return True
        return False

    def position_close_partial(self, ticket: int, volume: float, profit: float = 0.0) -> bool:
        for p in self.positions:
            if p.ticket == ticket:
                if volume >= p.volume:
                    return self.position_close(ticket, profit)
                p.volume = round(p.volume - volume, 8)
                self.deals.append(Deal(self.next_ticket(), p.symbol, p.magic, "OUT",
                                        p.ticket, profit, 0.0, 0.0, self.now))
                return True
        return False

    def fill_pending(self, ticket: int) -> Optional[int]:
        """Simula preenchimento de uma ordem Limit -> vira posição."""
        for o in self.pending_orders:
            if o.ticket == ticket:
                self.pending_orders.remove(o)
                ptype = PositionType.BUY if o.type == OrderType.BUY_LIMIT else PositionType.SELL
                tk = self.next_ticket()
                self.positions.append(Position(tk, o.symbol, o.magic, ptype,
                                                o.volume, o.price_open, o.sl, o.tp))
                self.deals.append(Deal(self.next_ticket(), o.symbol, o.magic, "IN", tk,
                                        0.0, 0.0, 0.0, self.now))
                return tk
        return None

    # ---------------- consultas (replicam o escopo real do MQ5, quirks inclusos) ----------------
    def get_position_by_magic_symbol(self, magic: int, symbol: str) -> Optional[Position]:
        """Equivalente a GetBotTicket() — ÚNICA função isolada por símbolo no original."""
        for p in self.positions:
            if p.magic == magic and p.symbol == symbol:
                return p
        return None

    def has_active_trade(self, magic: int, symbol: str) -> bool:
        """Equivalente a BotHasActiveTrade(): posição isolada por símbolo,
        MAS ordens pendentes filtradas SÓ por magic (quirk preservado)."""
        if self.get_position_by_magic_symbol(magic, symbol) is not None:
            return True
        return any(o.magic == magic for o in self.pending_orders)

    def find_bot_pending_order(self, magic: int) -> Optional[PendingOrder]:
        """Equivalente à busca em CheckPendingCancellation: primeira ordem do
        magic, SEM checar símbolo (quirk preservado)."""
        for o in self.pending_orders:
            if o.magic == magic:
                return o
        return None

    def close_all_by_magic(self, magic: int) -> None:
        """Equivalente a CloseAllOperations(): filtra SÓ por magic,
        atravessa símbolos (quirk preservado)."""
        for p in list(self.positions):
            if p.magic == magic:
                self.position_close(p.ticket)
        for o in list(self.pending_orders):
            if o.magic == magic:
                self.order_delete(o.ticket)

    def cancel_all_pending_by_magic(self, magic: int) -> None:
        for o in list(self.pending_orders):
            if o.magic == magic:
                self.order_delete(o.ticket)

    def floating_profit(self, magic: int) -> float:
        """Equivalente a GetFloatingProfit(): filtra SÓ por magic (quirk preservado)."""
        return sum(p.profit + p.swap for p in self.positions if p.magic == magic)

    def period_stats(self, start_time: datetime, magic: int) -> tuple[float, int, int]:
        """Equivalente a GetPeriodStats(): filtra SÓ por magic (quirk preservado)."""
        bot_position_ids = {d.position_id for d in self.deals
                             if d.magic == magic and d.entry == "IN" and d.time >= start_time}
        net = 0.0
        wins = 0
        loss = 0
        for d in self.deals:
            if d.entry not in ("OUT", "OUT_BY"):
                continue
            if d.position_id not in bot_position_ids:
                continue
            p = d.profit + d.swap + d.commission
            net += p
            if p > 0:
                wins += 1
            else:
                loss += 1
        return net, wins, loss

    def daily_trades_count(self, magic: int) -> int:
        day_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        return sum(1 for d in self.deals
                   if d.magic == magic and d.entry == "IN" and d.time >= day_start)

    # ---------------- séries de candles (equivalentes a iHigh/iLow/iClose/iTime/iBarShift) ----------------
    def set_bars(self, timeframe: str, candles: list[Candle]) -> None:
        """candles[0] = vela atual (em formação); candles[1] = última fechada; etc."""
        self.bars[timeframe] = candles

    def i_time(self, timeframe: str, shift: int) -> datetime:
        return self.bars[timeframe][shift].time

    def i_close(self, timeframe: str, shift: int) -> float:
        return self.bars[timeframe][shift].close

    def i_high(self, timeframe: str, shift: int) -> float:
        return self.bars[timeframe][shift].high

    def i_low(self, timeframe: str, shift: int) -> float:
        return self.bars[timeframe][shift].low

    def i_bar_shift(self, timeframe: str, ref_time: datetime) -> int:
        series = self.bars[timeframe]
        for idx, c in enumerate(series):
            if c.time <= ref_time:
                return idx
        return len(series) - 1

    def i_highest(self, timeframe: str, count: int, start: int) -> float:
        window = self.bars[timeframe][start:start + count]
        return max(c.high for c in window)

    def i_lowest(self, timeframe: str, count: int, start: int) -> float:
        window = self.bars[timeframe][start:start + count]
        return min(c.low for c in window)
