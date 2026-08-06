from fastapi import APIRouter, HTTPException, Request
from typing import Any, Dict

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


@router.get("/market/timeframes")
def get_timeframes():
    """
    Retorna todos os timeframes suportados pelo MetaTrader 5.
    """
    try:
        return market.supported_timeframes()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar os timeframes: {error}",
        ) from error


@router.get("/market/candles/{symbol}")
def get_candles(
    symbol: str,
    timeframe: int | None = None,
    bars: int = 300,
    offset: int = 0,
):
    """
    Retorna candles OHLC reais do MetaTrader 5.

    Parâmetros:
    - symbol: ativo solicitado;
    - timeframe: código de período do MetaTrader;
    - bars: quantidade de candles.
    """
    if bars < 1:
        raise HTTPException(status_code=400, detail="A quantidade de candles deve ser maior que zero.")

    # Resolve default timeframe lazily to avoid importing MetaTrader5 at module import time
    if timeframe is None:
        try:
            import MetaTrader5 as mt5

            timeframe = mt5.TIMEFRAME_M5
        except Exception:
            # When running tests without MT5, default to zero (adapter/market_service should handle)
            timeframe = 0

    try:
        dataframe = market.candles(
            symbol,
            timeframe,
            bars,
            offset=offset,
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


@router.get("/system/health")
def system_health(request: Request) -> Dict[str, Any]:
    """Return live system health including kernel, engines and adapter info.

    This endpoint is intentionally lightweight and defensive to avoid
    triggering expensive operations during health checks.
    """
    system = getattr(request.app.state, "system", None)

    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    application = system.get("application")
    market_engine = system.get("market_engine")
    event_bus = system.get("event_bus")

    status = application.system_status() if application is not None else {}

    # Adapter connection and symbol count (defensive)
    adapter = getattr(market_engine, "adapter", None)
    mt5_connected = None
    symbol_count = None
    latency_ms = None

    if adapter is not None:
        # Check connected flag if present
        mt5_connected = bool(getattr(adapter, "_connected", getattr(adapter, "connected", False)))

        try:
            import time

            t0 = time.perf_counter()
            symbols = adapter.get_symbols()
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000
            if isinstance(symbols, (list, tuple)):
                symbol_count = len(symbols)
                from datetime import datetime, timezone

                last_update = datetime.now(timezone.utc).isoformat()
            # connection info, timeframes
            try:
                conn_info = adapter.get_connection_info()
                broker_name = conn_info.get("company") or conn_info.get("name")
                terminal_status = conn_info.get("connected")
            except Exception:
                broker_name = None
                terminal_status = None

            try:
                timeframes = adapter.get_supported_timeframes()
                timeframe_count = len(timeframes) if isinstance(timeframes, dict) else None
            except Exception:
                timeframe_count = None
        except Exception:
            # Keep health endpoint tolerant: don't fail on adapter read errors
            pass

    uptime = None
    started_at = getattr(request.app.state, "started_at", None)
    if started_at is not None:
        from datetime import datetime, timezone

        uptime = (datetime.now(timezone.utc) - started_at).total_seconds()

    return {
        "kernel": status.get("kernel"),
        "failure_reason": status.get("failure_reason"),
        "engines": status.get("engines"),
        "eventbus": event_bus is not None,
        "adapter_connected": mt5_connected,
        "broker_name": locals().get("broker_name", None),
        "terminal_status": locals().get("terminal_status", None),
        "symbol_count": symbol_count,
        "timeframe_count": locals().get("timeframe_count", None),
        "last_symbol_update": locals().get("last_update", None),
        "latency_ms": latency_ms,
        "uptime_seconds": uptime,
    }


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