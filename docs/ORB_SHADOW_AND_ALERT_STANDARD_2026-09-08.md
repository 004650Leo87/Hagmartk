# ORB Shadow + Padrão Unificado de Alertas — 2026-09-08

## Escopo
- ORB_OPENING_RANGE_15M_5M_2R v1.0.0 promovida para SHADOW prospectivo PAPER.
- Universo ORB: Binance USD-M Futures perpétuos com perfil explícito 00:00 UTC.
- DVP, Teoria dos Ciclos e ORB permanecem sem execução real.
- real_order_execution_enabled=false é invariante.

## ORB prospectivo
- Faixa inicial: primeiros 15 minutos da sessão de pesquisa.
- Sinal: primeiro fechamento M5 válido entre T+20 e T+55.
- Entrada PAPER: primeira cotação Bid/Ask observada após o sinal, TTL de 5 segundos.
- Saída: STOP, TARGET 2R ou TIME em T+120.
- WebSocket público Binance !bookTicker fornece sequência Bid/Ask read-only.
- Gap/restart durante posição aberta gera ERROR_RECONCILE/UNRESOLVED, nunca resultado inventado.

## Padrão de comunicação
As três estratégias usam o mesmo template operacional:
- HAGMARTK DVP
- HAGMARTK TEORIA DOS CICLOS
- HAGMARTK ORB

Campos principais: ativo, horário de Brasília, direção, timeframe, entrada, stop, alvos e resultado quando disponível.
O Telegram não recebe mais estados internos desnecessários da Teoria dos Ciclos.
O Dashboard consome /api/alerts/recent e apresenta o mesmo vocabulário e filtros por estratégia.

## Evidência de validação
- Template unificado testado em DVP, TC e ORB.
- Frontend build PASS após o Centro de Ocorrências unificado.
- Telegram recebeu uma prévia explícita marcada como NÃO É EVENTO DE MERCADO.
- Antes do congelamento final, executar pytest completo, smoke do runtime, git diff --check e confirmar ordem real bloqueada.
