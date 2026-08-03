from datetime import datetime

import MetaTrader5 as mt5
import pandas as pd


class MarketDataService:

    def __init__(self):
        self.connected = False

    def connect_mt5(self):

        if mt5.initialize():
            self.connected = True
            return True

        return False

    def disconnect_mt5(self):

        if self.connected:
            mt5.shutdown()
            self.connected = False

    def symbols(self):

        if not self.connected:
            raise Exception("MetaTrader não conectado.")

        return mt5.symbols_get()

    def candles(
        self,
        symbol,
        timeframe,
        bars=500
    ):

        if not self.connected:
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

    def info(self):

        return {
            "connected": self.connected,
            "time": datetime.now()
        }