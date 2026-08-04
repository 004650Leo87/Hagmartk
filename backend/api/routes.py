from fastapi import APIRouter, HTTPException
import MetaTrader5 as mt5

from backend.services.account_service import AccountService
from backend.services.market_service import MarketService


router = APIRouter()

market = MarketService()
account = AccountService()


# =========================================================
# ROTAS DE MERCADO
# =========================================================

@router.get("/market/symbols")
def get_symbols():
    """
    Retorna todos os ativos disponíveis no MetaTrader 5.
    """
    try:
        return market.symbol_names()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar os ativos: {error}",
        ) from error


@router.get("/market/quote/{symbol}")
def get_quote(symbol: str):
    """
    Retorna a cotação atual de um ativo específico.
    """
    try:
        return market.quote(symbol)

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar a cotação: {error}",
        ) from error


@router.get("/market/quotes")
def get_quotes():
    """
    Retorna as cotações dos ativos favoritos do painel.
    """
    favoritos = [
        "XAUUSD",
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "BTCUSD",
    ]

    try:
        return market.quotes(favoritos)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar as cotações: {error}",
        ) from error


@router.get("/market/candles/{symbol}")
def get_candles(
    symbol: str,
    timeframe: int = mt5.TIMEFRAME_M5,
    bars: int = 300,
):
    """
    Retorna candles OHLC reais do MetaTrader 5.

    Parâmetros:
    - symbol: ativo solicitado;
    - timeframe: código de período do MetaTrader;
    - bars: quantidade de candles.
    """
    if bars < 1 or bars > 5000:
        raise HTTPException(
            status_code=400,
            detail=(
                "A quantidade de candles deve estar "
                "entre 1 e 5000."
            ),
        )

    try:
        dataframe = market.candles(
            symbol,
            timeframe,
            bars,
        )

        records = dataframe.to_dict("records")

        # Converte objetos Timestamp do pandas para texto ISO,
        # garantindo que o FastAPI consiga gerar o JSON.
        for candle in records:
            candle_time = candle.get("time")

            if candle_time is not None and hasattr(
                candle_time,
                "isoformat",
            ):
                candle["time"] = candle_time.isoformat()

        return records

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar os candles: {error}",
        ) from error


# =========================================================
# ROTAS DA CONTA
# =========================================================

@router.get("/account")
def get_account():
    """
    Retorna todas as informações disponíveis da conta
    conectada ao MetaTrader 5.
    """
    try:
        return account.account_info()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar os dados da conta: {error}",
        ) from error


@router.get("/account/summary")
def get_account_summary():
    """
    Retorna um resumo da conta pronto para o dashboard.
    """
    try:
        return account.account_summary()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar o resumo da conta: {error}",
        ) from error


@router.get("/account/positions")
def get_account_positions():
    """
    Retorna todas as posições abertas da conta.
    """
    try:
        return account.positions()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar as posições: {error}",
        ) from error


@router.get("/account/history/today")
def get_account_history_today():
    """
    Retorna o histórico e o resultado financeiro do dia.
    """
    try:
        return account.daily_history()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar o histórico diário: {error}",
        ) from error