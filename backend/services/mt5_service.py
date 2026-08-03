import MetaTrader5 as mt5


class MT5Service:

    def __init__(self):
        self.connected = False

    def connect(self):

        if self.connected:
            return True

        if mt5.initialize():

            self.connected = True
            return True

        return False

    def disconnect(self):

        if self.connected:
            mt5.shutdown()

        self.connected = False

    def is_connected(self):

        return self.connected