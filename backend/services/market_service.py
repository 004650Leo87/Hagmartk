import time
from datetime import datetime, timezone
from typing import Any

import MetaTrader5 as mt5
import pandas as pd

from backend.core.constants import categorize_symbol
from backend.indicators import EMAIndicator, RSIIndicator, SMAIndicator
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

    def detailed_symbols(self) -> list[dict[str, Any]]:
        raw_symbols = self.symbols()

        detailed: list[dict[str, Any]] = []

        for s in raw_symbols:
            name = getattr(s, "name", "") or str(s)
            path = getattr(s, "path", "") or ""
            description = getattr(s, "description", "") or ""

            info = mt5.symbol_info(name)
            if info is not None:
                path = getattr(info, "path", "") or path
                description = getattr(info, "description", "") or description
                visible = bool(getattr(info, "visible", getattr(s, "visible", False)))
                selected = bool(getattr(info, "selected", getattr(s, "selected", False)))
                digits = int(getattr(info, "digits", getattr(s, "digits", 0)))
                point = float(getattr(info, "point", getattr(s, "point", 0.0)))
                currency_base = getattr(info, "currency_base", "") or getattr(s, "currency_base", "") or ""
                currency_profit = getattr(info, "currency_profit", "") or getattr(s, "currency_profit", "") or ""
                trade_mode = getattr(info, "trade_mode", getattr(s, "trade_mode", None))
                spread = getattr(info, "spread", getattr(s, "spread", 0))
                volume_min = float(getattr(info, "volume_min", getattr(s, "volume_min", 0.0)))
                volume_max = float(getattr(info, "volume_max", getattr(s, "volume_max", 0.0)))
                volume_step = float(getattr(info, "volume_step", getattr(s, "volume_step", 0.0)))
                margin_initial = float(getattr(info, "margin_initial", getattr(s, "margin_initial", 0.0)))
                trade_contract_size = float(getattr(info, "trade_contract_size", getattr(s, "trade_contract_size", 0.0)))
            else:
                visible = bool(getattr(s, "visible", False))
                selected = bool(getattr(s, "selected", False))
                digits = int(getattr(s, "digits", 0))
                point = float(getattr(s, "point", 0.0))
                currency_base = getattr(s, "currency_base", "") or ""
                currency_profit = getattr(s, "currency_profit", "") or ""
                trade_mode = getattr(s, "trade_mode", None)
                spread = getattr(s, "spread", 0)
                volume_min = float(getattr(s, "volume_min", 0.0))
                volume_max = float(getattr(s, "volume_max", 0.0))
                volume_step = float(getattr(s, "volume_step", 0.0))
                margin_initial = float(getattr(s, "margin_initial", 0.0))
                trade_contract_size = float(getattr(s, "trade_contract_size", 0.0))

            detailed.append(
                {
                    "symbol": name,
                    "name": name,
                    "description": description,
                    "path": path,
                    "broker_path": path,
                    "category": categorize_symbol(path, name, description),
                    "visible": visible,
                    "selected": selected,
                    "digits": digits,
                    "point": point,
                    "currency_base": currency_base,
                    "currency_profit": currency_profit,
                    "trade_mode": trade_mode,
                    "spread": spread,
                    "volume_min": volume_min,
                    "volume_max": volume_max,
                    "volume_step": volume_step,
                    "margin_initial": margin_initial,
                    "trade_contract_size": trade_contract_size,
                }
            )

        return detailed

    def supported_timeframes(self) -> list[dict[str, Any]]:
        self._ensure_connection()

        timeframe_map: dict[int, str] = {}

        for attribute_name in dir(mt5):
            if attribute_name.startswith('TIMEFRAME_'):
                code = getattr(mt5, attribute_name)
                timeframe_map[int(code)] = attribute_name.replace(
                    'TIMEFRAME_',
                    '',
                )

        return [
            {'code': code, 'name': label}
            for code, label in sorted(
                timeframe_map.items(),
                key=lambda item: item[0],
            )
        ]

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
        offset: int = 0,
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

        # Retry curto e seguro (máximo 3 tentativas) para tolerar primeiro carregamento pós-select
        rates = None
        for attempt in range(3):
            rates = mt5.copy_rates_from_pos(
                symbol,
                timeframe,
                int(offset),
                int(bars),
            )
            if rates is not None and len(rates) > 0:
                break
            time.sleep(0.1)

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

    def candles_detailed(
        self,
        symbol: str,
        timeframe: int,
        bars: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Retorna histórico de candles estruturado com metadados para a pesquisa do Strategy Lab."""
        self._ensure_connection()

        symbol = symbol.upper().strip()

        if bars <= 0:
            raise ValueError("A quantidade de candles deve ser maior que zero.")

        symbol_info = mt5.symbol_info(symbol)

        if symbol_info is None:
            raise ValueError(f"O ativo '{symbol}' não foi encontrado no MetaTrader.")

        if not symbol_info.visible:
            selected = mt5.symbol_select(symbol, True)

            if not selected:
                raise RuntimeError(f"Não foi possível ativar o ativo '{symbol}'.")

        # Retry curto e seguro (máximo 3 tentativas)
        rates = None
        for attempt in range(3):
            rates = mt5.copy_rates_from_pos(
                symbol,
                timeframe,
                int(offset),
                int(bars),
            )
            if rates is not None and len(rates) > 0:
                break
            time.sleep(0.1)

        if rates is None or len(rates) == 0:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "requested_bars": bars,
                "returned_bars": 0,
                "offset": offset,
                "has_more": False,
                "earliest_timestamp": None,
                "latest_timestamp": None,
                "candles": [],
            }

        candle_list: list[dict[str, Any]] = []

        for r in rates:
            time_sec = int(r["time"])
            dt = datetime.fromtimestamp(time_sec, tz=timezone.utc)
            candle_list.append(
                {
                    "time": time_sec,
                    "datetime": dt.isoformat(),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "tick_volume": int(r["tick_volume"]),
                    "spread": int(r["spread"]),
                    "real_volume": int(r["real_volume"]),
                }
            )

        returned_bars = len(candle_list)
        earliest_ts = candle_list[0]["datetime"] if candle_list else None
        latest_ts = candle_list[-1]["datetime"] if candle_list else None

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "requested_bars": bars,
            "returned_bars": returned_bars,
            "offset": offset,
            "has_more": returned_bars >= bars,
            "earliest_timestamp": earliest_ts,
            "latest_timestamp": latest_ts,
            "candles": candle_list,
        }

    def get_indicators(
        self,
        symbol: str,
        timeframe: int,
        bars: int = 500,
        offset: int = 0,
        rsi_periods: list[int] | None = None,
        ema_periods: list[int] | None = None,
        sma_periods: list[int] | None = None,
    ) -> dict[str, Any]:
        """Calcula indicadores técnicos alinhados 1:1 com os timestamps dos candles."""
        if rsi_periods is None and ema_periods is None and sma_periods is None:
            rsi_periods = [14]
            ema_periods = [50, 200]
            sma_periods = []
        else:
            rsi_periods = rsi_periods or []
            ema_periods = ema_periods or []
            sma_periods = sma_periods or []

        max_warmup = 0
        for p in rsi_periods:
            max_warmup = max(max_warmup, p + 1)
        for p in ema_periods:
            max_warmup = max(max_warmup, p * 3)
        for p in sma_periods:
            max_warmup = max(max_warmup, p)

        total_bars_to_fetch = bars + max_warmup

        try:
            df_extended = self.candles(symbol, timeframe, bars=total_bars_to_fetch, offset=offset)
        except Exception:
            df_extended = pd.DataFrame()

        if df_extended.empty:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "bars": 0,
                "offset": offset,
                "candles": [],
                "indicators": {},
            }

        indicators_result: dict[str, list[dict[str, Any]]] = {}

        for p in rsi_periods:
            rsi_ind = RSIIndicator(period=p)
            series = rsi_ind.calculate(df_extended)
            indicators_result[f"rsi_{p}"] = []
            for i, val in enumerate(series):
                time_val = df_extended["time"].iloc[i]
                ts = int(time_val.timestamp()) if hasattr(time_val, "timestamp") else 0
                v = None if pd.isna(val) else round(float(val), 2)
                indicators_result[f"rsi_{p}"].append({"time": ts, "value": v})

        info = mt5.symbol_info(symbol) if hasattr(mt5, "symbol_info") else None
        digits = int(getattr(info, "digits", 5)) if info else 5

        for p in ema_periods:
            ema_ind = EMAIndicator(period=p)
            series = ema_ind.calculate(df_extended)
            indicators_result[f"ema_{p}"] = []
            for i, val in enumerate(series):
                time_val = df_extended["time"].iloc[i]
                ts = int(time_val.timestamp()) if hasattr(time_val, "timestamp") else 0
                v = None if pd.isna(val) else round(float(val), digits)
                indicators_result[f"ema_{p}"].append({"time": ts, "value": v})

        for p in sma_periods:
            sma_ind = SMAIndicator(period=p)
            series = sma_ind.calculate(df_extended)
            indicators_result[f"sma_{p}"] = []
            for i, val in enumerate(series):
                time_val = df_extended["time"].iloc[i]
                ts = int(time_val.timestamp()) if hasattr(time_val, "timestamp") else 0
                v = None if pd.isna(val) else round(float(val), digits)
                indicators_result[f"sma_{p}"].append({"time": ts, "value": v})

        df_target = df_extended.iloc[-bars:] if len(df_extended) > bars else df_extended

        candles_records = []
        for i in range(len(df_target)):
            time_val = df_target["time"].iloc[i]
            ts = int(time_val.timestamp()) if hasattr(time_val, "timestamp") else 0
            row = df_target.iloc[i]
            candles_records.append(
                {
                    "time": ts,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "tick_volume": int(row["tick_volume"]),
                    "spread": int(row["spread"]),
                    "real_volume": int(row["real_volume"]),
                }
            )

        aligned_indicators: dict[str, list[dict[str, Any]]] = {}
        for key, val_list in indicators_result.items():
            aligned_indicators[key] = val_list[-len(df_target):]

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": len(df_target),
            "offset": offset,
            "candles": candles_records,
            "indicators": aligned_indicators,
        }