# HAGMARTK Shadow Paper Execution V1 — 2026-09-04

## Objetivo

Operar o candidato congelado `hdf_dvp_exit_2r` contra mercado real em tempo real, simulando o lifecycle completo da operação sem transmitir qualquer ordem ao broker.

Fluxo operacional:
`HDF_DVP -> ARMED -> ACTIVATED -> MILESTONE_1R -> TARGET_2R | STOPPED`, com `EXPIRED` e `INVALIDATED` quando aplicável.

## Fronteira de segurança

- `broker_order_sent = false` em todo evento Paper.
- O Paper Engine não importa nem chama `MetaTrader5.order_send`.
- Execução ocorre somente em SQLite/local UI.
- Ordens reais continuam fora do escopo e exigirão gate explícito futuro.

## Mudança necessária para tempo real

O analisador histórico preserva seu comportamento original por padrão. O Shadow usa `include_open_tail=True` para analisar a cauda recente imediatamente, sem aguardar cinco candles futuros.

## Lifecycle Paper

- Setup novo nasce `ARMED` com activation level e stop estrutural congelados.
- Próximos candles fechados podem ativar a entrada virtual com política `NEXT_BAR` e tratamento de gap.
- Após ativação, o motor acompanha MFE/MAE, 1R, stop e alvo 2R.
- Target e stop na mesma barra usam política conservadora `STOP_FIRST`.
- Setup não ativado após cinco candles expira.
- Violação estrutural antes da entrada invalida o setup.
- Evento Paper já persistido mantém lifecycle após restart; novos setups retrospectivos continuam bloqueados pelo recovery cutoff.

## UI e observabilidade

O frontend passa a notificar mudanças `ARMED`, `ACTIVATED`, `TARGET_2R`, `STOPPED`, `EXPIRED` e `INVALIDATED`. A tela Shadow Strategies continua consumindo as estatísticas prospectivas reais do ledger Paper.

`WAITING_NEW_CANDLE` é tratado como scanner operacional quando não stale, pois representa espera normal pelo próximo fechamento.

## Validação

- suíte Paper/Recovery/HDF: 42 PASS;
- suíte de serviços: 159 PASS;
- regressão completa: 517 PASS, 1 skip esperado;
- frontend Vite build: PASS;
- nenhuma chamada de envio de ordem encontrada no caminho HDF/Paper.

Decisão: `SHADOW_PAPER_EXECUTION_V1 = ACCEPTED_FOR_DEPLOY`, mantendo trading real desabilitado.
