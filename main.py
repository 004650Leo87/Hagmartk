from engine.backtest import BacktestEngine
from data.loader import DataLoader
import MetaTrader5 as mt5
import pandas as pd

engine = BacktestEngine()

loader = DataLoader()

if loader.conectar_mt5():

    print("Conexão com o MetaTrader 5 realizada com sucesso!")

    rates = mt5.copy_rates_from_pos(
        "XAUUSD",
        mt5.TIMEFRAME_M15,
        0,
        1000
    )

    if rates is None:
        print("Não foi possível obter os candles.")
    else:

        df = pd.DataFrame(rates)

        df["time"] = pd.to_datetime(df["time"], unit="s")

        print(df.head())

        print()
        print(f"Total de candles: {len(df)}")

    loader.desconectar_mt5()