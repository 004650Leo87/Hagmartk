from fastapi import APIRouter
import MetaTrader5 as mt5

from backend.services.market_service import MarketService

router = APIRouter()

market = MarketService()


@router.get("/market/symbols")
def get_symbols():

    symbols = market.symbols()

    return {
        "total": len(symbols),
        "symbols": [s.name for s in symbols]
    }


@router.get("/market/candles")
def get_candles():

    df = market.candles(
        "XAUUSD",
        mt5.TIMEFRAME_M1,
        100
    )

    return df.to_dict(orient="records")