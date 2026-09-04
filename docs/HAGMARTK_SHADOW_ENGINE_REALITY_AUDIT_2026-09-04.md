# HAGMARTK SHADOW — Auditoria de Realidade do Motor DVP

Data: 2026-09-04
Status: VERIFIED / READ-ONLY MARKET EXECUTION
Candidato preservado: `hdf_dvp_exit_2r` v1.0.0

## Objetivo

Verificar se o HAGMARTK Shadow possui um motor real de detecção ou apenas apresentação textual, e registrar as lacunas antes de ampliar alvos/probabilidades.

## Resultado executivo

O motor é real: recebe OHLC/volume do MT5, calcula RSI Wilder, confirma pivôs sem lookahead, detecta divergência regular, mede volume relativo, reconhece padrão de reversão, arma o setup, acompanha ativação e executa o lifecycle PAPER sem ordem no broker.

A cadeia auditada foi:

`MT5 -> candles fechados -> RSI/pivôs -> divergência -> volume -> padrão -> ARMED -> PaperExecution -> Telegram`

Não foi encontrada chamada `mt5.order_send()` no backend operacional do Shadow. `real_order_execution_enabled=false` permanece ativo.
## Evidência empírica com dados reais do MT5

Auditoria isolada, sem gravar no banco produtivo e sem Telegram, usando os mesmos parâmetros do scanner atual:

- 39 combinações (13 ativos x M15/H1/H4)
- 5.000 candles solicitados por combinação
- 194.961 candles fechados analisados
- 52.340 pivôs confirmados
- 3.986 divergências D
- 1.827 ocorrências D+V
- 621 ocorrências D+P
- 305 ocorrências D+V+P
- 213 ocorrências ativadas
- 0 erros de leitura/processamento

Replay isolado de mercado real confirmou o pipeline completo. Exemplo EURJPY H1 em 2026-09-02:

- direção: BULLISH
- confluência: 15:00 UTC
- padrão: HAMMER
- volume relativo: 1.553x
- ativação: 184.097
- stop: 183.882
- estado no candle da confluência: ARMED
- candle seguinte 16:00 UTC: ACTIVATED em 184.097
## Auditoria de alvos — base histórica observada

Foi aplicada política conservadora `STOP_FIRST` e horizonte máximo de 20 candles após a entrada. Estes valores são taxas históricas observadas, não probabilidades individualizadas nem promessa futura.

| Alvo | Atingiu | Amostra | Taxa observada | IC 95% Wilson |
|---|---:|---:|---:|---:|
| T1 = 1R | 101 | 213 | 47,4% | 40,8%–54,1% |
| T2 = 2R | 58 | 213 | 27,2% | 21,7%–33,6% |
| T3 = 3R | 33 | 213 | 15,5% | 11,2%–21,0% |
| T4 = 4R | 25 | 213 | 11,7% | 8,1%–16,8% |

Por timeframe, a amostra de ativações foi: M15=79, H1=82, H4=52. O sistema ainda não possui um modelo calibrado por evento para converter essas frequências em probabilidade individual.

## Lacuna crítica: Fibonacci

O candidato congelado V1 declara explicitamente `fibonacci_status = UNRESOLVED (Not Used in Candidate V1)`.

Portanto, o DVP atualmente promovido para evento significa, na prática, `Divergência + Volume + Padrão`. Fibonacci existe como telemetria/pesquisa isolada e NÃO participa do gate que cria o evento.

Qualquer promoção de Fibonacci para confluência obrigatória deve gerar novo candidato/versionamento; não alterar silenciosamente `hdf_dvp_exit_2r` v1.0.0.
## Outras lacunas encontradas

1. O runtime do Shadow monitora apenas `M15`, `H1` e `H4`, embora a estratégia declare suporte a M5/M15/M30/H1/H2/H4/D1/W1.
2. O lifecycle PAPER encerra operacionalmente em 2R; ele não continua observando 3R/4R para calibração prospectiva.
3. O Telegram ainda não possui outbox durável com retry/backoff persistente; falha externa não derruba o Shadow, mas pode perder uma notificação.
4. O scheduler busca 100 candles por combinação a cada ciclo de 3 s. É suficiente para o warmup mínimo, porém merece revisão de estabilidade do RSI e eficiência de polling.
5. Existem módulos legados `divap` paralelos ao caminho HDF atual; o runtime auditado usa `backend.strategies.hdf.strategy`, mas a duplicidade deve ser tratada como risco de manutenção.

## Decisão para quatro alvos

Não usar percentuais inventados ou `confidence=1.0` como probabilidade de mercado.

Criar camada separada `DvpTargetReachCalibration`, sem alterar a regra do candidato V1:

- T1 = 1R
- T2 = 2R
- T3 = 3R
- T4 = 4R
- para cada alvo: preço, taxa observada, tamanho da amostra, IC 95%, fonte e horizonte
- priorizar amostra LIVE/FORWARD; histórico serve como prior/base rate identificado
- segmentação progressiva: timeframe -> direção -> classe de ativo -> padrão/volume, somente quando houver amostra suficiente
- fallback explícito para amostra mais ampla quando o estrato for pequeno

O Telegram poderá mostrar essas projeções como `probabilidade estimada/calibrada`, nunca como certeza.
## Estado congelado nesta auditoria

- Template Telegram V2 aprovado e congelado no commit `bc6deb4`.
- Candidato `hdf_dvp_exit_2r` v1.0.0 preservado sem alteração de parâmetros/hash.
- Nenhuma ordem real habilitada.
- Scanner produtivo permaneceu saudável após os testes: 39 registrados, 0 erros, Telegram READY.

## Próximo gate recomendado

Antes de chamar qualquer percentual de `probabilidade do evento`, implementar e validar a camada de calibração de alvos e a observação pós-2R. Em paralelo, abrir pesquisa controlada para Fibonacci e para expansão dos timeframes. Somente após evidência objetiva promover qualquer uma dessas mudanças para um novo candidato.
