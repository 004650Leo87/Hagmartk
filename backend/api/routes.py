from fastapi import APIRouter, HTTPException, Request
from typing import Any, Dict

from backend.schemas.backtest import BacktestRequest
from backend.services.account_service import AccountService
from backend.services.backtest_service import BacktestService
from backend.services.market_service import MarketService
from backend.services.strategy_service import StrategyService


router = APIRouter()

market = MarketService()
account = AccountService()
strategy_service = StrategyService()
backtest_service = BacktestService()


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


@router.get("/market/symbols/detailed")
def get_symbols_detailed():
    """
    Retorna o catálogo detalhado de ativos com metadados e categorias.
    """
    try:
        return market.detailed_symbols()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar o catálogo de ativos detalhados: {error}",
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


@router.get("/market/candles/{symbol}/detailed")
def get_candles_detailed(
    symbol: str,
    timeframe: int | None = None,
    bars: int = 500,
    offset: int = 0,
):
    """
    Retorna histórico de candles estruturado com estatísticas e metadados para o Strategy Lab.
    """
    if bars < 1:
        raise HTTPException(status_code=400, detail="A quantidade de candles deve ser maior que zero.")

    if timeframe is None:
        try:
            import MetaTrader5 as mt5

            timeframe = mt5.TIMEFRAME_M5
        except Exception:
            timeframe = 5

    try:
        return market.candles_detailed(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            offset=offset,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar o histórico detalhado: {error}",
        ) from error


@router.get("/market/indicators/{symbol}")
def get_market_indicators(
    symbol: str,
    timeframe: int | None = None,
    bars: int = 500,
    offset: int = 0,
    rsi: str | None = "14",
    ema: str | None = "50,200",
    sma: str | None = None,
):
    """
    Retorna candles e indicadores técnicos (RSI, EMA, SMA) rigorosamente alinhados por timestamp.
    """
    if bars < 1:
        raise HTTPException(status_code=400, detail="A quantidade de candles deve ser maior que zero.")

    if timeframe is None:
        try:
            import MetaTrader5 as mt5

            timeframe = mt5.TIMEFRAME_M5
        except Exception:
            timeframe = 5

    def parse_periods(param: str | None) -> list[int]:
        if not param:
            return []
        try:
            return [int(p.strip()) for p in param.split(",") if p.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Parâmetro de período inválido: {param}")

    rsi_periods = parse_periods(rsi)
    ema_periods = parse_periods(ema)
    sma_periods = parse_periods(sma)

    try:
        return market.get_indicators(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            offset=offset,
            rsi_periods=rsi_periods,
            ema_periods=ema_periods,
            sma_periods=sma_periods,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Erro ao calcular indicadores: {error}") from error


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

        # Fallback: check live MetaTrader 5 terminal status if adapter._connected flag is False
        if not mt5_connected:
            try:
                import MetaTrader5 as mt5

                term_info = mt5.terminal_info()
                acc_info = mt5.account_info()
                if term_info is not None or acc_info is not None:
                    mt5_connected = True
            except Exception:
                pass

        try:
            import time

            t0 = time.perf_counter()
            symbols = adapter.get_symbols()
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000
            if isinstance(symbols, (list, tuple)):
                symbol_count = len(symbols)
                if symbol_count > 0:
                    mt5_connected = True
                from datetime import datetime, timezone

                last_update = datetime.now(timezone.utc).isoformat()
            # connection info, timeframes
            try:
                conn_info = adapter.get_connection_info()
                broker_name = conn_info.get("company") or conn_info.get("name")
                terminal_status = conn_info.get("connected")
                if terminal_status:
                    mt5_connected = True
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


# =========================================================
# ROTAS DO STRATEGY LAB & BACKTEST
# =========================================================

@router.get("/api/strategies")
def list_strategies():
    """
    Lista todas as estratégias registradas no Strategy Lab.
    """
    try:
        return strategy_service.list_strategies()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar estratégias: {error}",
        ) from error


@router.get("/api/strategies/{strategy_id}")
def get_strategy_details(strategy_id: str, version: str | None = None):
    """
    Retorna os detalhes e metadados de uma estratégia.
    """
    strat = strategy_service.get_strategy(strategy_id, version)
    if not strat:
        raise HTTPException(status_code=404, detail=f"Estratégia '{strategy_id}' não encontrada.")
    return strat


@router.post("/api/backtest/run")
def run_backtest_experiment(req: BacktestRequest):
    """
    Executa um experimento de backtest bar-by-bar (sem lookahead bias).
    """
    try:
        return backtest_service.run_backtest(
            strategy_id=req.strategy_id,
            symbol=req.symbol,
            timeframe=req.timeframe,
            bars=req.bars,
            offset=req.offset,
            intrabar_policy=req.intrabar_policy,
            spread_points=req.spread_points,
            commission_per_trade=req.commission_per_trade,
            slippage_points=req.slippage_points,
            in_sample_ratio=req.in_sample_ratio,
            version=req.version,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Erro durante o backtest: {error}") from error


@router.get("/api/backtest/experiments")
def list_experiments():
    """
    Lista todos os experimentos de backtest realizados nesta sessão.
    """
    try:
        return backtest_service.list_experiments()
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Erro ao listar experimentos: {error}") from error


@router.get("/api/backtest/experiments/{experiment_id}")
def get_experiment_by_id(experiment_id: str):
    """
    Retorna um experimento específico por seu identificador único.
    """
    exp = backtest_service.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experimento '{experiment_id}' não encontrado.")
    return exp


@router.get("/strategy-lab/divergences/{symbol}")
def detect_divergences(
    symbol: str,
    timeframe: str = "M15",
    bars: int = 500,
    offset: int = 0,
    pivot_left: int = 2,
    pivot_right: int = 2,
    min_bars_between: int = 5,
    max_bars_between: int = 50,
):
    """
    Detecta e retorna as divergências Nível 1 (HDM 0.1.0) para pesquisa e evidência visual.
    """
    tf_upper = timeframe.upper().strip()
    from backend.core.constants import SUPPORTED_TIMEFRAMES
    from backend.strategies.hdm_divergence import HDMDivergenceStrategy

    tf_code = SUPPORTED_TIMEFRAMES.get(tf_upper)
    if tf_code is None:
        raise HTTPException(status_code=400, detail=f"Timeframe '{timeframe}' não é suportado.")

    strategy = HDMDivergenceStrategy(
        pivot_left=pivot_left,
        pivot_right=pivot_right,
        min_bars_between_pivots=min_bars_between,
        max_bars_between_pivots=max_bars_between,
    )

    if not strategy.validate_timeframe(tf_upper):
        raise HTTPException(
            status_code=400,
            detail=f"Timeframe '{tf_upper}' não é permitido para detecção HDM. Permitidos: {strategy.allowed_timeframes}",
        )

    try:
        df = market.candles(symbol, tf_code, bars=bars + strategy.warmup_bars, offset=offset)
        events = []
        for t_idx in range(strategy.warmup_bars, len(df)):
            history_t = df.iloc[: t_idx + 1]
            found = strategy.evaluate(history_t, symbol, tf_upper, is_closed_bar=True)
            for evt in found:
                events.append(
                    {
                        "strategy_id": evt.strategy_id,
                        "strategy_version": evt.strategy_version,
                        "symbol": evt.symbol,
                        "timeframe": evt.timeframe,
                        "direction": evt.direction.value,
                        "detected_at": evt.detected_at,
                        "reference_price": evt.reference_price,
                        "reasons": evt.reasons,
                        "metadata": evt.metadata,
                    }
                )

        return {
            "symbol": symbol,
            "timeframe": tf_upper,
            "parameters": strategy.parameters,
            "events": events,
            "count": len(events),
        }
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Erro na detecção de divergências: {error}") from error