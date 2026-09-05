# HAGMARTK MF — Binance USD-M Futures Public V1

Data: 2026-09-04

## Decisão

Fonte cripto primária do painel: **Binance USDⓈ-M Futures — contratos PERPETUAL**, somente dados públicos.

Motivo: o produto acompanha mercado futuro; Spot não é a melhor representação operacional para preço, volume, funding e mark price de perpétuos.

## Fronteira de segurança

- autenticação: NONE;
- nenhuma API Key ou Secret;
- nenhum endpoint de conta;
- nenhum endpoint de ordem;
- `real_order_execution_enabled=false`;
- integração é Market Data / READ-ONLY.

## Evidência de conectividade no Leocripto

- `/fapi/v1/ping`: HTTP 200;
- `/fapi/v1/time`: HTTP 200;
- `/fapi/v1/klines` BTCUSDT M5: HTTP 200;
- `/fapi/v1/exchangeInfo`: HTTP 200;
- 569 perpétuos `TRADING` observados no catálogo;
- 526 deles cotados em USDT.

## Arquitetura implementada

A integração não substitui o MT5. O `MarketService` atua como roteador de fontes:

- instrumentos MT5 permanecem no provider `MT5_TICKMILL`;
- perpétuos Binance usam `BINANCE_USDM_FUTURES`;
- cada item detalhado recebe `provider`, `market_type` e `instrument_id`;
- `BTCUSD` do MT5 e `BTCUSDT` da Binance não são tratados como o mesmo instrumento.

O catálogo do painel passa a ser a união dos providers disponíveis. No teste de implantação foram observados 686 instrumentos: 117 do MT5 + 569 perpétuos Binance, sem colisão de símbolos nessa fotografia.

## Funções públicas integradas

- catálogo de perpétuos `TRADING`;
- Bid/Ask/Last por `bookTicker`/`ticker/price`;
- candles normalizados em UTC;
- volume base, volume cotado, número de trades e taker-buy volume;
- mark price, index price, funding rate e próximo funding;
- M5, M15, M30, H1, H2, H4, D1 e W1, entre outros intervalos suportados.

O frontend identifica a fonte e permite localizar `BTCUSDT` e outros contratos Binance Futures no mesmo catálogo usado pelo gráfico.

## Gate WebSocket / Shadow

O caminho REST está comprovado na máquina de produção. O socket público `fstream.binance.com` aceitou conexão e SUBSCRIBE, porém não entregou payload de mercado dentro da janela de teste local.

Consequentemente, **não** foi autorizada nesta entrega a expansão dos scanners DVP/Teoria dos Ciclos para centenas de contratos Binance por polling REST. Fazer isso a cada poucos segundos criaria pressão desnecessária de rate limit e misturaria uma nova fonte à validação científica existente.

Próximo gate para estratégias cripto:

1. provar recepção contínua do WebSocket Futures no Leocripto;
2. implementar reconexão, heartbeat, deduplicação e gap recovery por REST;
3. provar candle fechado sem lookahead;
4. iniciar universo cripto controlado em Shadow;
5. somente depois ampliar o universo dinamicamente.

Os candidatos congelados DVP e Cycle Theory não são alterados por esta integração de Market Data.

## Resultado da implantação

- adapter público USD-M Futures: funcional;
- MarketService multi-provider: funcional;
- painel/catalogação multi-provider: implementado;
- execução de corretora: bloqueada;
- API key necessária: não;
- conta Binance necessária: não.

## Validação pós-implantação

Runtime após reinício:

- `MT5_TICKMILL`: conectado, 117 instrumentos;
- `BINANCE_USDM_FUTURES`: conectado, 569 perpétuos;
- catálogo combinado: 686 instrumentos;
- `BTCUSDT` quote: provider Binance Futures;
- `BTCUSDT` M5: candles reais retornando;
- mark/index/funding: retornando;
- `EURUSD` quote/candles: continua no MT5;
- Cycle Theory Shadow: ativo, 0 erros, ordem real false;
- DVP Shadow: 104 combinações, 0 erros;
- Telegram: ready.

Regressão final:

- Python: 550 passed, 1 skipped, 0 failures;
- frontend Vite build: PASS;
- busca por endpoint/chamada de ordem ou credencial no adapter Binance: nenhuma ocorrência;
- hashes congelados DVP e Cycle Theory: inalterados.
