# HAGMARTK Shadow — Coverage Denominator Gate — 2026-09-04

## Problema

A telemetria global somava `expected_checks` apenas das linhas existentes em `shadow_scanner_telemetry`.

Consequência: se uma combinação esperada não produzisse linha alguma, ela desaparecia do denominador e a cobertura poderia parecer 100% mesmo com um slot perdido.

Durante o deploy do recovery cutoff, 26 linhas pós-corte representavam corretamente M15 + H1. A ausência de H4 às 12:00 UTC não era falha: neste broker, após normalização de +3h, H4 segue fase 01/05/09/13/17/21 UTC.

## Contrato congelado

1. O denominador de coverage é independente das linhas persistidas.
2. Slots esperados são derivados do T0 da telemetria até `now`.
3. A fase temporal de cada combinação é inferida do `last_processed_candle` já persistido no scanner state.
4. Uma combinação suportada sem linha de telemetria continua contando no denominador quando um fechamento era esperado.
5. H4 não assume mais artificialmente fechamento em horas UTC divisíveis por 4.

## Implementação

- `_scanner_close_anchor(...)` usa a abertura do último candle processado + duração do timeframe como âncora de fechamento.
- `_count_expected_boundaries(...)` calcula quantos fechamentos deveriam ter ocorrido entre T0 e o instante consultado.
- `_expected_checks_for_window(...)` usa a mesma fase para registrar sucessos/falhas no slot correto.
- `_expected_checks_since_telemetry_t0(...)` preenche o denominador mesmo quando não existe linha persistida.
- `get_shadow_telemetry(...)` usa `max(stored_expected, derived_expected)` e continua excluindo combinações unsupported.

## Validação

Teste direcionado de telemetria: 15 PASS.

Suíte completa de serviços: 151 PASS.

Regressão completa do repositório: 508 PASS, 1 skip esperado.

O fingerprint do SQLite real ficou idêntico antes/depois da regressão: 26 linhas, 26 sucessos, 0 falhas, HDF live = 0 e Fibonacci live = 0.

## Decisão

`COVERAGE_DENOMINATOR_V2 = ACCEPTED`.

Este gate não altera candidato, parâmetros, hash, lógica de entrada/saída nem autorização de execução. Apenas torna a cobertura fail-closed quando uma combinação esperada deixa de produzir telemetria.
