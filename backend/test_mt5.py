from backend.services.market_data import MarketDataService

service = MarketDataService()

print("Conectando...")

if service.connect_mt5():

    print("Conectado!")

    print(service.info())

    symbols = service.symbols()

    print(f"Quantidade de ativos: {len(symbols)}")

    print(symbols[:10])

    service.disconnect_mt5()

else:

    print("Erro ao conectar.")