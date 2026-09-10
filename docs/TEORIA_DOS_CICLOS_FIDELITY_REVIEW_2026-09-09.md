# HAGMARTK — Teoria dos Ciclos — Fidelity Review

Data: 2026-09-09
Status: OPEN / FAIL-CLOSED PARA TELEGRAM
Escopo: comparar o candidato `cycle_theory_v111_baseline` com conteúdo público atribuído a Marcelo Ferreira/Fimathe, sem alterar silenciosamente o candidato V111.

## Evidência primária/relevante consultada

1. Marcelo Ferreira — vídeo público “A VERDADE por trás Estratégia dos CICLOS”.
   - URL: https://www.youtube.com/watch?v=eovvSv62p9Q
   - Transcript público consultado via PickScribe.
2. Canal/Telegram público Marcelo Ferreira | Fimathe.
   - Referência pública para live “A TEORIA DOS CICLOS FIMATHE - LIVE 04/01”.
   - URL: https://www.youtube.com/watch?v=gvjMjx6ta40
3. Conteúdo público “Os 3 Ciclos Fimathe”.
   - URL: https://www.youtube.com/watch?v=ginFNrsiX5A
4. Source audit interno do arquivo `TEORIA_DOS_CICLOS_ULTIMATE_1.mq5`, versão 111.00.

## Achados de alta confiança

- O material público de Marcelo ancora a leitura na formação da vela semanal.
- O Canal de Abertura é tratado como referência central da semana.
- A primeira hora é descrita como quatro velas de M15 usadas para encontrar/formar esse canal.
- O rompimento do Canal de Abertura forma o primeiro ciclo na direção do rompimento.
- O material público descreve C2 e ciclos posteriores como projeções acumuladas dos ciclos anteriores.
- Há exemplos públicos de reversão através do Canal de Abertura e busca de ciclos no lado oposto.

## Divergências V111 x método público

- O V111 inicia `ref_time_start` ao entrar em STARTING e, após reset, volta a construir outro canal.
- O V111 constrói o canal com os extremos das quatro velas fechadas anteriores após a contagem mínima.
- Portanto, o canal V111 não está garantidamente ancorado no mesmo Canal de Abertura semanal durante toda a semana.
- O modo padrão V111 é `GATILHO_EXPANSAO` + `ENTRY_PULLBACK_25`.
- Na expansão V111, `exp_level` fica a uma altura de canal além do extremo e `super_size` pode equivaler aproximadamente a duas alturas do canal.
- Alvos V111 são recalculados como `entry +/- super_size * i`.
- Essas regras podem ser fiéis ao EA V111 auditado, mas não estão comprovadas como equivalentes à formulação pública da Teoria dos Ciclos de Marcelo Ferreira.

## Defeito visual confirmado

O renderer HAGMARTK rotulava o retângulo `channel_high/channel_low` como “ZONA NEUTRA / CANAL NEUTRO”, embora o baseline esteja em modo Expansão. Também desenhava `c1_mid`, definido como ponto médio entre o canal e `exp_level`, como uma linha chamada “C1”.

Correção aplicada e endurecida:
- o print V111 NÃO usa mais os nomes `Canal de Abertura` ou `C1` como se fossem equivalentes ao método semanal;
- `channel_high/channel_low` é rotulado `CANAL V111 (4 BARRAS)`;
- a região projetada é `FAIXA DE EXPANSÃO V111`;
- `mid_line50` é `DIVISÃO 50% V111`;
- `exp_level` é `EXPANSÃO V111`.

Essa correção é visual/semântica e não altera a matemática do candidato V111.

## Contenção operacional aplicada

- O catálogo do provedor pode continuar amplo, mas o live V111 passa a usar uma allowlist explícita.
- Allowlist default: EURUSD, GBPUSD, USDJPY, EURGBP, USDCHF, AUDUSD, USDCAD, NZDUSD, GBPJPY e XAUUSD.
- Override só por `HAGMARTK_CYCLE_LIVE_SYMBOLS`.
- Ticks de recovery/catch-up continuam reconstruindo ledger/estado, porém `publish_notifications=False`.
- Telegram da Teoria dos Ciclos fica desligado por padrão durante esta revisão.
- Reativação exige `HAGMARTK_CYCLE_TELEGRAM_ENABLED=1` deliberadamente.
- Parciais e breakeven deixam de ser eventos publicáveis; o canal operacional prioriza entrada, marcos relevantes e encerramento.
- Atualizações de qualquer estratégia sem mensagem raiz conhecida são descartadas pelo notifier para evitar mensagens órfãs.

## Decisão arquitetural

NÃO alterar `cycle_theory_v111_baseline` para “parecer” com vídeos públicos. Ele permanece um candidato de fidelidade ao arquivo V111.

Se a auditoria confirmar um contrato público suficientemente preciso, criar uma estratégia separada, por exemplo `cycle_theory_weekly_public_v1`, com identidade/hash/testes próprios. Isso evita contaminar evidência histórica e permite comparar V111 versus método semanal lado a lado.

## Pendências de fidelidade antes de uma implementação pública

Ainda precisam de definição primária suficiente: regra exata de ancoragem temporal por mercado/fuso, fechamento que confirma C1/C2, geometria completa de C2/C3/subníveis, stop/reversão, tratamento de gap semanal e adaptação ou rejeição para mercados 24/7.

Até isso estar documentado e testado, alertas V111 não devem ser apresentados como “Teoria dos Ciclos validada de Marcelo Ferreira”.

## Achado crítico adicional — domínio temporal

O baseline V111 possui controles intradiários explícitos:
- `start_time = 01:00`;
- `end_entry_time = 23:00`;
- `close_all_time = 23:50`.

Em `risk_protections.py`, ao atingir `close_all_time`, o EA fecha posições por magic e entra em `STATE_OFF`. Na janela seguinte, estando ligado e em `STATE_OFF`, executa `reset_cycle()`.

Isso contrasta diretamente com a descrição pública de Marcelo, cuja unidade estrutural é a vela semanal e cujo Canal de Abertura é formado no início da semana. Portanto, a divergência é de domínio temporal, não somente de nomenclatura ou renderização.

## Evidência de mercado desta semana

Dados M15 reais do MT5/Tickmill, semana iniciada em 2026-09-06:
- EURUSD: primeiros quatro M15 contínuos 21:00–22:00 UTC; CA público-ref = 1.16052–1.16130.
- GBPUSD: 21:00–22:00 UTC; CA público-ref = 1.35089–1.35142.
- USDJPY: 21:00–22:00 UTC; CA público-ref = 155.945–156.109.
- XAUUSD: 22:00–23:00 UTC; CA público-ref = 4416.89–4435.21.

Conclusão: a abertura semanal deve ser derivada da primeira sequência de quatro M15 realmente disponível por instrumento/provedor. Um horário UTC global fixo seria incorreto.
## Comparação A/B — referência semanal pública vs V111

Na mesma semana:
- EURUSD: referência pública começa 2026-09-06 21:00 UTC; `ref_time_start` V111 observado = 2026-09-09 09:10 (tempo de servidor armazenado pelo motor).
- USDJPY: referência pública começa 2026-09-06 21:00 UTC; V111 apresentou duas referências internas distintas no meio do período observado.
- AUDUSD e NZDUSD também apresentaram múltiplos `ref_time_start` V111.

A comparação confirma que o estado V111 pode reconstruir seu canal durante a semana e não representa persistentemente o Canal de Abertura semanal descrito no conteúdo público.

## Modelo público de referência criado

Foi criado `backend/strategies/cycle_theory/public_reference.py` exclusivamente para auditoria e comparação.

Propriedades:
- exige quatro M15 contínuos para formar o canal inicial;
- detecta rompimento somente por fechamento fora do canal;
- projeta uma geometria acumulada C1/C2/C3 marcada explicitamente como `REFERENCE_ONLY_SECONDARY_GEOMETRY`;
- não envia ordens;
- não publica Telegram;
- não substitui nem altera `cycle_theory_v111_baseline`.

A progressão acumulada permanece hipótese de referência até validação primária suficiente de todos os subníveis e regras operacionais.
## Política transversal de qualidade do Telegram

A pesquisa quantitativa permanece desacoplada da publicação operacional.

Raízes DVP passam a exigir:
- evento prospectivo, não bootstrap/sintético;
- timestamp recente;
- pivôs e preços válidos;
- volume relativo positivo;
- padrão de candle definido;
- entrada/ativação, stop e alvo 2R válidos.

Raízes ORB passam a exigir:
- timestamp recente;
- range válido (`high > low`);
- `signal_id`, `signal_time`, `t0`;
- entrada, stop e alvo válidos.

Por padrão uma nova mensagem raiz não pode representar evento com mais de 900 segundos. Atualizações só são aceitas se já existir uma raiz da operação.