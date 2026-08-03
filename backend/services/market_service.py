import pandas as pd
import MetaTrader5 as mt5

from backend.services.mt5_service import MT5Service


class MarketService:

    def __init__(self):

        self.mt5 = MT5Service()

    def symbols(self):

        if not self.mt5.connect():
            raise Exception("MetaTrader não conectado.")

        return mt5.symbols_get()

    def candles(
        self,
        symbol,
        timeframe,
        bars=500
    ):

        if not self.mt5.connect():
            raise Exception("MetaTrader não conectado.")

        rates = mt5.copy_rates_from_pos(
            symbol,
            timeframe,
            0,
            bars
        )

        df = pd.DataFrame(rates)

        df["time"] = pd.to_datetime(
            df["time"],
            unit="s"
        )

        return df