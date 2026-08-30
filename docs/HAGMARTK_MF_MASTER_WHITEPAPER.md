# HAGMARTK MF â€” MASTER WHITEPAPER

**Status:** fonte documental executiva e tÃ©cnica vigente
**VersÃ£o:** 2026-08-29 EOD
**Projeto:** HAGMARTK Mercado Financeiro (HAGMARTK MF)

## 1. Identidade e missÃ£o
HAGMARTK MF Ã© uma estaÃ§Ã£o de inteligÃªncia quantitativa de mercado. O produto ingere dados reais, normaliza proveniÃªncia, pesquisa e valida estratÃ©gias sob hipÃ³teses explÃ­citas, identifica eventos quantitativos repetÃ­veis, acompanha seu ciclo de vida e publica inteligÃªncia verificÃ¡vel. NÃ£o Ã© clone do TradingView, sala de sinais nem terminal de execuÃ§Ã£o manual.

## 2. Regra mÃ¡xima: realidade antes da narrativa
Nenhum fato de mercado, evento, lucro, probabilidade, custo, fill ou estatÃ­stica pode ser inventado. BACKTEST, RESEARCH, SHADOW e LIVE sÃ£o domÃ­nios separados e sempre rotulados. Resultado modelado nunca Ã© chamado de resultado real. Eventos invÃ¡lidos/perdedores permanecem no histÃ³rico. A ausÃªncia de evento Ã© um resultado vÃ¡lido.

## 3. Ciclo obrigatÃ³rio
`DATA -> NORMALIZE -> RESEARCH -> FIDELITY -> VALIDATE -> SHADOW -> EVENT -> MANAGE -> PUBLISH -> REVIEW`
Nenhuma interface, automaÃ§Ã£o, IA ou publicaÃ§Ã£o pode pular um estÃ¡gio.

## 4. Produto e superfÃ­cies
- Intelligence Cockpit: estado atual e fatos que importam.
- Strategy Lab: estratÃ©gia versionada, testes, robustez e fidelidade.
- Event Radar: candidatos reais por ativo/timeframe, com proveniÃªncia.
- Evidence Inspector: amostra, regimes, falhas, expectativa e linhagem.
- Live Event Desk: DETECTED -> FORMING -> CONFIRMED -> ACTIVE -> RESOLVED.
- Research Queue: hipÃ³teses e experimentos controlados.
- System Health: feeds, latÃªncia, stale data, relÃ³gio, custos e incidentes.

## 5. ConstituiÃ§Ã£o de interface
Nenhum botÃ£o decorativo. Todo controle visÃ­vel exige `capability_id`, mÃ³dulo proprietÃ¡rio, contratos de entrada/saÃ­da, testes, estÃ¡gio permitido, estado de falha, telemetria e link de evidÃªncia. Sem isso, fica oculto/desabilitado.

## 6. EstratÃ©gias vigentes
**HDF/DVP:** candidato congelado `hdf_dvp_exit_2r` v1.0.0, `ROBUST_CANDIDATE`. NÃ£o alterar lÃ³gica, EXIT_2R, candidate_id, version/hash ou Universo Shadow por housekeeping.

**Teoria dos Ciclos V111:** referÃªncia local identificada como `#property version "111.00"`; implementaÃ§Ã£o HAGMARTK permanece RESEARCH/FIDELITY. NÃ£o hÃ¡ autorizaÃ§Ã£o para afirmar lucro real. OtimizaÃ§Ã£o Ã© proibida antes dos gates crÃ­ticos de fidelidade econÃ´mica.

## 7. Estado de fidelidade da Teoria dos Ciclos
PROVEN inclui ordering OnTick, normalizaÃ§Ã£o de lote, cÃ¡lculo real de margem via MT5 sem envio de ordem, lado de entrada, submissÃ£o de limit, spread gate, stops/freeze, parciais, TP final, cancelamento de pullback, reset pÃ³s-fechamento e visibilidade OHLC progressiva.

Ainda PARTIAL/MODELLED: pending fill real, breakeven/trailing aceito pelo servidor, caminho intrabar, execuÃ§Ã£o SL/TP em gap, comissÃ£o/swap no replay, slippage/gaps, deviation/filling server behavior, ATR terminal exato, UTCâ†”TimeCurrent broker-server e warmup. Esses itens bloqueiam alegaÃ§Ãµes econÃ´micas definitivas.

## 8. EvidÃªncia real capturada em 29/08
- MT5 `order_calc_margin`, EURUSD BUY 1.0 lote, Ask 1.15824: USD 231.65 em conta 1:500; nenhuma ordem enviada.
- EURUSD: Bid 1.15820, Ask 1.15824, Point 0.00001, spread terminal=4 e cÃ¡lculo independente=4 pontos.
- HistÃ³rico MT5 90 dias: 69 deals de saÃ­da; XAUUSD 61 saÃ­das com comissÃ£o agregada -USD 1.83 e swap -USD 0.54. Isso prova que replay zero-cost nÃ£o Ã© economicamente fiel; nÃ£o prova custos especÃ­ficos da V111.
- API Python MT5 entrega epochs de tick/candle em UTC; isso nÃ£o prova o offset/DST de `TimeCurrent()` do EA.

## 9. Event Protocol
Unidade pÃºblica Ã© **Market Event / Evento de Mercado**, nÃ£o â€œsinalâ€. Classes: MARKET_BRIEF, RADAR, QUANT_EVENT, EVENT_UPDATE, EVENT_AUTOPSY, RESEARCH_UPDATE, SYSTEM_STATUS. SÃ³ QUANT_EVENT pode carregar estrutura completa de referÃªncia/invalidaÃ§Ã£o/objetivos. Ledger Ã© append-only; nÃ£o apagar fracassos.

Todo Quant Event exige IDs/versionamento, ativo/timeframe, timestamps/domÃ­nio temporal, estado, fatos gatilho, regiÃ£o de referÃªncia, invalidaÃ§Ã£o, objetivos quando aplicÃ¡vel, proveniÃªncia, amostra quando houver estatÃ­stica, hipÃ³teses de custo/fill/dados, limitaÃ§Ãµes e elegibilidade de publicaÃ§Ã£o.

## 10. Dados e provedores
Arquitetura alvo: `Provider -> Provider Adapter -> Normalized Market Contract -> Market Engine -> Research/Event Engine -> Publication`.
MT5 continua vÃ¡lido, mas nÃ£o define sozinho o universo futuro. EstratÃ©gias devem ser provider-neutral. Direitos de exibiÃ§Ã£o/redistribuiÃ§Ã£o sÃ£o gate obrigatÃ³rio antes de livestream/publicaÃ§Ã£o. Nunca inferir que API gratuita permite uso pÃºblico.

## 11. PublicaÃ§Ã£o, broadcast e mobile
Telegram, social, YouTube e assinantes consomem somente Publication API/Event Bus read-only. Nunca mutam pesquisa/estratÃ©gia/trading. Broadcast futuro: Event Engine -> Broadcast View -> Broadcast Controller -> OBS -> YouTube. OBS Ã© transmissÃ£o; HAGMARTK Ã© fonte de verdade.

Chat ao vivo: AUTO apenas para fatos comprovados pelo HAGMARTK; ASSISTED para rascunho sujeito a gates; HUMAN para aconselhamento individual, previsÃ£o sensÃ­vel ou recomendaÃ§Ã£o. Moment Engine e Content Repurposing devem usar timestamps reais do Evidence Ledger, nÃ£o narrativas fabricadas.

## 12. SeguranÃ§a e execuÃ§Ã£o
NÃ£o existe autorizaÃ§Ã£o para execuÃ§Ã£o autÃ´noma com dinheiro real. Ferramentas de evidÃªncia nÃ£o podem criar caminho de envio de ordens. Backend atual nÃ£o deve ser exposto publicamente antes de autenticaÃ§Ã£o/autorizaÃ§Ã£o. Credenciais e tokens nÃ£o entram no Git. HAGMARTK FLOW/NEXORA, Service Baby e demais produtos permanecem isolados.

## 13. Infraestrutura e custo
Cloud-ready e PC-independent Ã© direÃ§Ã£o arquitetural; dependÃªncia Windows/MT5 deve ficar isolada em adapter. Cloudflare pode servir edge/routing/security/static, mas nÃ£o substitui compute quantitativo pesado. Custo inicial prÃ³ximo de zero; tecnologia paga sÃ³ entra apÃ³s benefÃ­cio mensurÃ¡vel e comparaÃ§Ã£o com alternativa gratuita.

n8n, Obsidian, Buffer e Floot sÃ£o ferramentas opcionais, nunca dependÃªncias do nÃºcleo por conveniÃªncia.

## 14. Ordem de construÃ§Ã£o congelada
1. Fechar/bound gates crÃ­ticos da Cycle Theory V111 sem otimizar.
2. Inventariar dashboard e Capability Registry.
3. Remover/ocultar/reclassificar controles Ã³rfÃ£os.
4. Strategy Registry + Evidence Registry + Event schema.
5. Event Engine/Radar sobre estratÃ©gias validadas/shadow.
6. Live Event Desk + lifecycle replayÃ¡vel.
7. Broadcast/publication adapters apÃ³s seguranÃ§a, dados e compliance.
8. Discovery automation sÃ³ quando o pipeline souber rejeitar falsos positivos.

## 15. CritÃ©rio econÃ´mico
Pergunta â€œa estratÃ©gia dÃ¡ lucro?â€ sÃ³ pode ser respondida com escopo e proveniÃªncia. Exigir, conforme estÃ¡gio: amostra, PnL lÃ­quido, spread, comissÃ£o, swap, slippage/fills, drawdown, expectativa, distribuiÃ§Ã£o, regimes e OOS/walk-forward. Nunca fundir backtest/shadow/live sem rÃ³tulo.

## 16. GovernanÃ§a e fechamento
MudanÃ§as relevantes exigem testes, compile/diff checks, auditoria de credenciais/runtime, commit seguro e push quando autorizado. O fechamento diÃ¡rio atualiza Whitepaper, Master Prompt e checkpoint. Este Whitepaper, Product North, Event Protocol e Parity Matrix sÃ£o a referÃªncia vigente; documentos antigos conflitantes ficam explicitamente SUPERSEDED.
