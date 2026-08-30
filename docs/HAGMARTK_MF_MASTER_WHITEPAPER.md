# HAGMARTK MF — MASTER WHITEPAPER

**Status:** fonte documental executiva e técnica vigente
**Versão:** 2026-08-29 EOD
**Projeto:** HAGMARTK Mercado Financeiro (HAGMARTK MF)

## 1. Identidade e missão
HAGMARTK MF é uma estação de inteligência quantitativa de mercado. O produto ingere dados reais, normaliza proveniência, pesquisa e valida estratégias sob hipóteses explícitas, identifica eventos quantitativos repetíveis, acompanha seu ciclo de vida e publica inteligência verificável. Não é clone do TradingView, sala de sinais nem terminal de execução manual.

## 2. Regra máxima: realidade antes da narrativa
Nenhum fato de mercado, evento, lucro, probabilidade, custo, fill ou estatística pode ser inventado. BACKTEST, RESEARCH, SHADOW e LIVE são domínios separados e sempre rotulados. Resultado modelado nunca é chamado de resultado real. Eventos inválidos/perdedores permanecem no histórico. A ausência de evento é um resultado válido.

## 3. Ciclo obrigatório
`DATA -> NORMALIZE -> RESEARCH -> FIDELITY -> VALIDATE -> SHADOW -> EVENT -> MANAGE -> PUBLISH -> REVIEW`
Nenhuma interface, automação, IA ou publicação pode pular um estágio.

## 4. Produto e superfícies
- Intelligence Cockpit: estado atual e fatos que importam.
- Strategy Lab: estratégia versionada, testes, robustez e fidelidade.
- Event Radar: candidatos reais por ativo/timeframe, com proveniência.
- Evidence Inspector: amostra, regimes, falhas, expectativa e linhagem.
- Live Event Desk: DETECTED -> FORMING -> CONFIRMED -> ACTIVE -> RESOLVED.
- Research Queue: hipóteses e experimentos controlados.
- System Health: feeds, latência, stale data, relógio, custos e incidentes.

## 5. Constituição de interface
Nenhum botão decorativo. Todo controle visível exige `capability_id`, módulo proprietário, contratos de entrada/saída, testes, estágio permitido, estado de falha, telemetria e link de evidência. Sem isso, fica oculto/desabilitado.

## 6. Estratégias vigentes
**HDF/DVP:** candidato congelado `hdf_dvp_exit_2r` v1.0.0, `ROBUST_CANDIDATE`. Não alterar lógica, EXIT_2R, candidate_id, version/hash ou Universo Shadow por housekeeping.

**Teoria dos Ciclos V111:** referência local identificada como `#property version "111.00"`; implementação HAGMARTK permanece RESEARCH/FIDELITY. Não há autorização para afirmar lucro real. Otimização é proibida antes dos gates críticos de fidelidade econômica.

## 7. Estado de fidelidade da Teoria dos Ciclos
PROVEN inclui ordering OnTick, normalização de lote, cálculo real de margem via MT5 sem envio de ordem, lado de entrada, submissão de limit, spread gate, stops/freeze, parciais, TP final, cancelamento de pullback, reset pós-fechamento e visibilidade OHLC progressiva.

Ainda PARTIAL/MODELLED: pending fill real, breakeven/trailing aceito pelo servidor, caminho intrabar, execução SL/TP em gap, comissão/swap no replay, slippage/gaps, deviation/filling server behavior, ATR terminal exato, UTC↔TimeCurrent broker-server e warmup. Esses itens bloqueiam alegações econômicas definitivas.

## 8. Evidência real capturada em 29/08
- MT5 `order_calc_margin`, EURUSD BUY 1.0 lote, Ask 1.15824: USD 231.65 em conta 1:500; nenhuma ordem enviada.
- EURUSD: Bid 1.15820, Ask 1.15824, Point 0.00001, spread terminal=4 e cálculo independente=4 pontos.
- Histórico MT5 90 dias: 69 deals de saída; XAUUSD 61 saídas com comissão agregada -USD 1.83 e swap -USD 0.54. Isso prova que replay zero-cost não é economicamente fiel; não prova custos específicos da V111.
- API Python MT5 entrega epochs de tick/candle em UTC; isso não prova o offset/DST de `TimeCurrent()` do EA.

## 9. Event Protocol
Unidade pública é **Market Event / Evento de Mercado**, não “sinal”. Classes: MARKET_BRIEF, RADAR, QUANT_EVENT, EVENT_UPDATE, EVENT_AUTOPSY, RESEARCH_UPDATE, SYSTEM_STATUS. Só QUANT_EVENT pode carregar estrutura completa de referência/invalidação/objetivos. Ledger é append-only; não apagar fracassos.

Todo Quant Event exige IDs/versionamento, ativo/timeframe, timestamps/domínio temporal, estado, fatos gatilho, região de referência, invalidação, objetivos quando aplicável, proveniência, amostra quando houver estatística, hipóteses de custo/fill/dados, limitações e elegibilidade de publicação.

## 10. Dados e provedores
Arquitetura alvo: `Provider -> Provider Adapter -> Normalized Market Contract -> Market Engine -> Research/Event Engine -> Publication`.
MT5 continua válido, mas não define sozinho o universo futuro. Estratégias devem ser provider-neutral. Direitos de exibição/redistribuição são gate obrigatório antes de livestream/publicação. Nunca inferir que API gratuita permite uso público.

## 11. Publicação, broadcast e mobile
Telegram, social, YouTube e assinantes consomem somente Publication API/Event Bus read-only. Nunca mutam pesquisa/estratégia/trading. Broadcast futuro: Event Engine -> Broadcast View -> Broadcast Controller -> OBS -> YouTube. OBS é transmissão; HAGMARTK é fonte de verdade.

Chat ao vivo: AUTO apenas para fatos comprovados pelo HAGMARTK; ASSISTED para rascunho sujeito a gates; HUMAN para aconselhamento individual, previsão sensível ou recomendação. Moment Engine e Content Repurposing devem usar timestamps reais do Evidence Ledger, não narrativas fabricadas.

## 12. Segurança e execução
Não existe autorização para execução autônoma com dinheiro real. Ferramentas de evidência não podem criar caminho de envio de ordens. Backend atual não deve ser exposto publicamente antes de autenticação/autorização. Credenciais e tokens não entram no Git. HAGMARTK FLOW/NEXORA, Service Baby e demais produtos permanecem isolados.

## 13. Infraestrutura e custo
Cloud-ready e PC-independent é direção arquitetural; dependência Windows/MT5 deve ficar isolada em adapter. Cloudflare pode servir edge/routing/security/static, mas não substitui compute quantitativo pesado. Custo inicial próximo de zero; tecnologia paga só entra após benefício mensurável e comparação com alternativa gratuita.

n8n, Obsidian, Buffer e Floot são ferramentas opcionais, nunca dependências do núcleo por conveniência.

## 14. Ordem de construção congelada
1. Fechar/bound gates críticos da Cycle Theory V111 sem otimizar.
2. Inventariar dashboard e Capability Registry.
3. Remover/ocultar/reclassificar controles órfãos.
4. Strategy Registry + Evidence Registry + Event schema.
5. Event Engine/Radar sobre estratégias validadas/shadow.
6. Live Event Desk + lifecycle replayável.
7. Broadcast/publication adapters após segurança, dados e compliance.
8. Discovery automation só quando o pipeline souber rejeitar falsos positivos.

## 15. Critério econômico
Pergunta “a estratégia dá lucro?” só pode ser respondida com escopo e proveniência. Exigir, conforme estágio: amostra, PnL líquido, spread, comissão, swap, slippage/fills, drawdown, expectativa, distribuição, regimes e OOS/walk-forward. Nunca fundir backtest/shadow/live sem rótulo.

## 16. Governança e fechamento
Mudanças relevantes exigem testes, compile/diff checks, auditoria de credenciais/runtime, commit seguro e push quando autorizado. O fechamento diário atualiza Whitepaper, Master Prompt e checkpoint. Este Whitepaper, Product North, Event Protocol e Parity Matrix são a referência vigente; documentos antigos conflitantes ficam explicitamente SUPERSEDED.
