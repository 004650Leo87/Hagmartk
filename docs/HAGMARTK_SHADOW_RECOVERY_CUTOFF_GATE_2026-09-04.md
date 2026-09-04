# HAGMARTK Shadow Recovery Cutoff Gate — 2026-09-04

## Problema observado

Após um restart do backend, o scanner reconstruiu um RADAR `EURUSD M15 / HDF_DV` cuja decisão era `2026-09-04T10:15:00Z`, mas o registro foi criado somente às `11:06:46Z`.

O backend estava desligado no instante da decisão. Portanto o registro era recovery/backfill e não evidência prospectiva verdadeira.

Também foi encontrado desalinhamento entre o scanner e o modelo atual `HDFOccurrence`: os tempos canônicos estão em `temporal_model`, enquanto o scanner ainda consultava alguns atributos top-level legados.

## Contrato congelado

1. `runtime_started_at` é capturado a cada instância do `ShadowScannerManager`.
2. Em sessão Shadow recuperada, um novo registro cuja decisão é anterior ao runtime atual é ignorado como `RECOVERY_BACKFILL_IGNORED`.
3. Um `ShadowEvent` previamente persistido pode continuar seu lifecycle após restart.
4. Fibonacci pré-runtime só pode evoluir se a telemetria correspondente já existia antes do restart.
5. HDFEvidence novo pré-runtime não entra como `LIVE_PROSPECTIVE`.
6. O instante canônico de decisão do DVP é `temporal_model.confluence_completed_at`.
7. Pivôs visuais permanecem evidência, mas não substituem o timestamp de decisão.
8. Ativação usa `temporal_model.activation_time` / `entry_at`.
9. `ShadowEvent` é construído diretamente dos campos reais de `HDFOccurrence`; referências legadas `occ.divergence`/`occ.pattern` não são usadas.
10. A representação do benchmark 2R usa a entrada real e o risco real quando o evento já foi ativado; para ARMED permanece projeção baseada em activation level/stop.
11. Estados canônicos `TARGET_2` e `STOPPED` são aceitos; aliases legados continuam tolerados apenas por compatibilidade.

## Migração preservativa

Backup antes da migração: `shadow_engine_pre_recovery_cutoff_20260904_113719.db`.

SHA-256: `f3e152b9b584960e1e63c13bda7b263949db66e3d00ac699aa544737a41e6365`.

O registro `ev_bull_EURUSD_M15_20260904_0945000000` foi preservado e reclassificado de `LIVE_PROSPECTIVE` para `RECOVERY_BACKFILL_IGNORED`, com reason codes explícitos. Nenhuma linha foi apagada.

Após a migração: HDF live = 0; Fibonacci live = 0.
## Validação

Suíte direcionada recovery/HDF/Fibonacci: 25 PASS.

Suíte ampla de serviços Shadow/Event/Fibonacci: 156 PASS.

Regressão completa do repositório: 505 PASS, 1 skip esperado.

O fingerprint operacional do SQLite permaneceu idêntico antes/depois da regressão completa, provando que pytest não voltou a tocar no banco real.

## Decisão

`RECOVERY_CUTOFF_V1 = ACCEPTED`.

Este gate é de integridade metodológica e não altera candidato, versão, parâmetros ou hash. A estratégia permanece em Shadow e continua sem autorização para operação real.

## Deploy final e corte de telemetria

Código versionado/push: commit `2f8b964` (`fix shadow recovery cutoff`).

O primeiro restart comprovou o cutoff: Radar live = 0 e Fibonacci live = 0; o EURUSD recovery não reapareceu.

A cobertura inicial ficou em 80% porque a sessão operacional anterior incluía um slot M15 perdido em cada um dos 13 ativos durante a manutenção programada. Não havia `failed_checks` novos.

Como `2f8b964` é um novo deploy, as 39 linhas dessa sessão foram preservadas em `legacy_pre_recovery_deploy_20260904_115621` e a telemetria ativa recebeu T0 próprio `2026-09-04T11:56:21Z`.

Backup pré-corte: `shadow_engine_pre_recovery_deploy_20260904_115621.db`; SHA-256 `ca2201b27a448ad7121f70cf0655e6184751e13802b001a70faca5d9b2729f41`.

Após o corte: HDF live = 0, Fibonacci live = 0, Radar live = 0, 39 scanners ativos, 0 erros, 0 unsupported. Até o primeiro fechamento de candle pós-deploy, coverage permanece `UNKNOWN`, o que é o estado correto para uma sessão sem amostra observada.
