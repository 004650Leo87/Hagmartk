import pandas as pd
import MetaTrader5 as mt5


class DataLoader:

    def conectar_mt5(self):

        if not mt5.initialize():
            print("Erro ao conectar ao MT5.")
            return False

        print("MT5 conectado com sucesso!")
        return True

    def desconectar_mt5(self):

        mt5.shutdown()

    def load_csv(self, caminho):

        df = pd.read_csv(caminho)

        print(f"{len(df)} candles carregados.")

        return df