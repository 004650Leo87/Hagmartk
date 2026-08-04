from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import MetaTrader5 as mt5
import pandas as pd

from backend.services.mt5_service import MT5Service


class MarketService:
    def __init__(self) -> None:
        self.mt5 = MT5Service()

    def _ensure_connection(self) -> None:
        if not self.mt5.connect():
            error_code, error_message = mt5.last_error()

            raise RuntimeError(
                f"Não foi possível conectar ao MetaTrader 5. "
                f"Código: {error_code}. Mensagem: {error_message}"
            )

    def symbols(self):
        self._ensure_connection()

        symbols = mt5.symbols_get()

        if symbols is None:
            error_code, error_message = mt5.last_error()

            raise RuntimeError(
                f"Não foi possível carregar os ativos. "
                f"Código: {error_code}. Mensagem: {error_message}"
            )

        return symbols

    def symbol_names(self) -> list[str]:
        symbols = self.symbols()

        return [symbol.name for symbol in symbols]

    def quote(self, symbol: str) -> dict[str, Any]:
        self._ensure_connection()

        symbol = symbol.upper().strip()

        symbol_info = mt5.symbol_info(symbol)

        if symbol_info is None:
            raise ValueError(
                f"O ativo '{symbol}' não foi encontrado no MetaTrader."
            )

        if not symbol_info.visible:
            selected = mt5.symbol_select(symbol, True)

            if not selected:
                raise RuntimeError(
                    f"Não foi possível ativar o ativo '{symbol}' "
                    f"na Observação do Mercado."
                )

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            error_code, error_message = mt5.last_error()

            raise RuntimeError(
                f"Não foi possível obter a cotação de '{symbol}'. "
                f"Código: {error_code}. Mensagem: {error_message}"
            )

        bid = float(tick.bid)
        ask = float(tick.ask)
        last = float(tick.last)
        point = float(symbol_info.point)

        spread_points = 0.0

        if point > 0:
            spread_points = (ask - bid) / point

        tick_time = datetime.fromtimestamp(
            tick.time,
            tz=timezone.utc,
        ).isoformat()

        return {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "last": last,
            "spread": round(ask - bid, symbol_info.digits),
            "spread_points": round(spread_points, 2),
            "digits": int(symbol_info.digits),
            "point": point,
            "time": tick_time,
        }

    def quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        quotes: list[dict[str, Any]] = []

        for symbol in symbols:
            try:
                quotes.append(self.quote(symbol))
            except (ValueError, RuntimeError) as error:
                quotes.append(
                    {
                        "symbol": symbol.upper().strip(),
                        "error": str(error),
                    }
                )

        return quotes

    def candles(
        self,
        symbol: str,
        timeframe: int,
        bars: int = 500,
    ) -> pd.DataFrame:
        self._ensure_connection()

        symbol = symbol.upper().strip()

        if bars <= 0:
            raise ValueError(
                "A quantidade de candles deve ser maior que zero."
            )

        symbol_info = mt5.symbol_info(symbol)

        if symbol_info is None:
            raise ValueError(
                f"O ativo '{symbol}' não foi encontrado no MetaTrader."
            )

        if not symbol_info.visible:
            selected = mt5.symbol_select(symbol, True)

            if not selected:
                raise RuntimeError(
                    f"Não foi possível ativar o ativo '{symbol}'."
                )

        rates = mt5.copy_rates_from_pos(
            symbol,
            timeframe,
            0,
            bars,
        )

        if rates is None or len(rates) == 0:
            error_code, error_message = mt5.last_error()

            raise RuntimeError(
                f"Não foi possível carregar os candles de '{symbol}'. "
                f"Código: {error_code}. Mensagem: {error_message}"
            )

        dataframe = pd.DataFrame(rates)

        dataframe["time"] = pd.to_datetime(
            dataframe["time"],
            unit="s",
            utc=True,
        )

        return dataframe