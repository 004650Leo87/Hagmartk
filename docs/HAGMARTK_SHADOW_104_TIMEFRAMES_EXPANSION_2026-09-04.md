# HAGMARTK SHADOW — Expansão Operacional para 104 Combinações

Data: 2026-09-04
Status: IMPLEMENTADO / VALIDADO / SHADOW-PAPER

## Escopo aprovado

O universo operacional do Shadow passou a monitorar 13 ativos em 8 timeframes:

- M5
- M15
- M30
- H1
- H2
- H4
- D1
- W1

Total: **13 × 8 = 104 combinações**.

Esta mudança amplia apenas o universo de observação. O candidato congelado não foi alterado.
## Invariantes preservadas

- Candidate ID: `hdf_dvp_exit_2r`
- Versão: `1.0.0`
- Parameter hash: `d192dd381b33a430e8214b7a3ad1d850e03db48eb601696dc2cc57adf160955a`
- Validação de imutabilidade: PASS
- Execução real na corretora: `false`
- Telegram: somente alertas SHADOW / PAPER
- Fibonacci: continua fora do gate do candidato V1; permanece pesquisa paralela

## Alterações técnicas

- Duração de timeframes centralizada em `TIMEFRAME_MINUTES`.
- Scanner passa a usar os 8 timeframes aprovados.
- Fechamento de candle é calculado pela duração real de cada timeframe.
- Timeframe desconhecido falha fechado, sem fallback silencioso para M15.
- H2 foi incluído no mapeamento textual do adapter MT5.
- Staleness/telemetria foram atualizados para os 8 timeframes.
- Health/progress deixaram de assumir 39 combinações fixas.
- Dashboard foi corrigido para não exibir 39/3 TF ou Telegram OFF quando o runtime informa outra realidade.
## Validação com dados reais do MT5 — novos timeframes

Auditoria isolada com até 5.000 candles por ativo/timeframe, sem gravar eventos no banco produtivo e sem enviar Telegram:

| TF | Candles | D | DV | DP | DVP | Ativados | Erros |
|---|---:|---:|---:|---:|---:|---:|---:|
| M5 | 64.987 | 1.225 | 534 | 223 | 93 | 61 | 0 |
| M30 | 64.987 | 1.259 | 707 | 210 | 105 | 71 | 0 |
| H2 | 64.987 | 1.300 | 633 | 201 | 101 | 63 | 0 |
| D1 | 61.948 | 1.155 | 558 | 136 | 72 | 54 | 0 |
| W1 | 14.967 | 249 | 115 | 29 | 15 | 12 | 0 |

Conclusão: o mesmo motor DVP encontra ocorrências matemáticas reais em todos os cinco timeframes adicionados. Eles não são apenas rótulos de interface.

Exemplo real auditado em M5: GBPUSD bearish, DVP completo, volume relativo 2,202x, Bearish Engulfing e ativação posterior registrada pelo motor histórico.
## Prova de runtime após implantação

Leitura do backend já reiniciado com o novo escopo:

- Scanners registrados: **104**
- Scanners ativos: **104**
- Scanners recentemente varridos: **104**
- Stale: **0**
- Erros: **0**
- Telegram ready: **true** (`BOT_API`)
- Execução real: **false**

O estado `WAITING_NEW_CANDLE` é operacional: significa que a combinação foi varrida e está aguardando o próximo fechamento válido. Não representa scanner parado.

Benchmark de leitura das 104 combinações no MT5: aproximadamente 20,5 s para um sweep completo de 100 candles por combinação, sem erro de provider.

## Testes

- Suíte Python completa: **534 passed, 1 skipped, 0 failed**.
- Contrato específico de fechamento de candle cobre os 8 timeframes.
- Frontend Vite: build PASS.
- Aviso residual: bundle JS ~505 kB; tratar futuramente com code splitting, sem impacto funcional no Shadow atual.
## Próxima camada sem alterar o candidato V1

Os quatro alvos e probabilidades por alvo permanecem requisito aprovado, mas não serão apresentados como probabilidades específicas do trade até existir calibração estatística defensável.

Base rates históricas já medidas sobre 213 ativações do candidato atual, horizonte de 20 candles e política conservadora STOP_FIRST:

- T1 / 1R: 47,4%
- T2 / 2R: 27,2%
- T3 / 3R: 15,5%
- T4 / 4R: 11,7%

Esses percentuais são frequências históricas agregadas, não previsão individual de uma nova ocorrência.

A próxima implementação deve manter separadas: detecção DVP, lifecycle PAPER do candidato congelado e calibração de alcance T1–T4.