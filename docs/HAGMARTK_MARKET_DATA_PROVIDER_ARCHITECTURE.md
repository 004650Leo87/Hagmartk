# HAGMARTK MF — Market Data Provider Architecture

Status: architecture contract / pre-implementation
Date: 2026-08-29

## Decision
HAGMARTK MF must not depend on one broker terminal or one market-data vendor. MT5 remains an important provider, but the product universe is a union of normalized providers.

Core flow:
`Provider -> Provider Adapter -> Normalized Market Contract -> Market Engine -> Research/Event Engine -> Publication surfaces`

The existing `MarketAdapter` contract and `MT5MarketAdapter` are the starting point. New providers must implement the adapter boundary; strategy code must not import provider SDKs directly.

## Immediate provider strategy
- MT5: broker-specific FX, metals, indices and existing Shadow compatibility.
- Alpaca: primary zero-cost development candidate for US equities and ETFs; free real-time feed is IEX-only, with broader historical support.
- Binance public market data: primary development candidate for crypto spot market breadth and streaming.
- Dukascopy: research candidate for deep Forex historical bid/ask and tick evidence.
- Twelve Data: useful multi-asset validation/fallback candidate, but free/basic licensing is internal non-display and cannot be assumed valid for public YouTube redistribution.

No provider is declared production/publication-ready until licensing, provenance, latency and data-quality gates pass.
## Required normalized contract
Every observation must carry at least: provider id, provider symbol, canonical symbol, asset class, exchange/venue where applicable, timeframe, timestamp with declared time domain, OHLCV/quote fields actually supplied, data freshness, and provenance state.

Canonical symbols must be independent of vendor notation. Examples: `AAPL`, `META`, `EURUSD`, `BTCUSDT`; provider aliases are mapping metadata, not strategy identifiers.

Provider capabilities must be explicit rather than inferred: quotes, candles, ticks, trades, bid/ask, volume semantics, real-time/delayed/EOD status, historical depth, stream support and licensing/display status.

## Publication/data-rights gate
Research access and public display are different permissions. A free API key does not imply permission to redistribute real-time market data on YouTube, Telegram, Instagram or a public website.

Before a provider feeds Broadcast Mode or external publication, record:
- source terms/licence reviewed;
- external display/redistribution allowed or prohibited;
- real-time vs delayed status;
- attribution requirements;
- commercial-use restrictions;
- applicable exchange entitlements.

If rights are unclear, the provider is `RESEARCH_ONLY` and its raw feed must not be published externally.

## Engineering consequence
Direct `MetaTrader5` imports still present in API routes are migration debt. They must progressively move behind provider-neutral timeframe/symbol/data contracts before multi-provider Event Engine rollout. This refactor must not alter frozen HDF behavior or enable order execution.
## Implementation order
1. Preserve current MT5 behavior as baseline.
2. Extend `MarketAdapter` metadata/capability contract without breaking existing callers.
3. Introduce provider registry/router and canonical symbol mapping.
4. Add Alpaca read-only adapter and contract tests.
5. Add Binance public read-only adapter and contract tests.
6. Evaluate Dukascopy historical ingestion for Forex fidelity datasets.
7. Only then allow Event Engine universe selection across providers.
8. Public Broadcast/Publication surfaces consume only providers that pass the data-rights gate.

## Current research findings (2026-08-29)
- Alpaca Basic: US stocks/ETFs, free IEX real-time stream, 30 WebSocket symbols, historical data since 2016; full SIP is paid.
- Twelve Data Basic: real-time US equities/ETFs, Forex and crypto for internal non-display use; 8 API credits/minute and 800/day, limited trial WebSocket.
- Massive Basic: all US stock tickers or all Forex/crypto tickers depending product, 5 API calls/minute, 2 years history, EOD-focused free tier.
- Finnhub has broad symbol discovery/quotes/streams, but stock/forex/crypto candles are currently premium endpoints; not selected as primary OHLC research source.
- Dukascopy exposes historical bid/ask and tick data useful for fidelity research.

This document records architecture, not a promise that any provider remains free or redistribution-licensed indefinitely. Provider terms must be revalidated before production/publication.