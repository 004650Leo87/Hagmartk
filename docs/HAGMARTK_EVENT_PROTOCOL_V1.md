# HAGMARTK Event Protocol v1

Status: PRODUCT CONTRACT / PRE-IMPLEMENTATION
Date: 2026-08-29

## 1. Purpose

The Event Protocol is the single contract between quantitative engines and every HAGMARTK presentation/distribution surface.

A strategy never publishes directly to dashboard, Telegram, YouTube, Instagram or another channel.
It produces evidence. The Event Engine may transform eligible evidence into a Market Event.

The objective is frequent, useful market intelligence without manufacturing trade opportunities.
Frequency comes from multiple event/content classes, never from lowering quantitative gates.

## 2. Public-language rule (Brazil)

Internal engineering may use English terminology. Public-facing communication must prefer simple Brazilian Portuguese.

Preferred public terms:
- Evento de Mercado
- Radar Quantitativo
- Em formação
- Confirmado
- Região de referência
- Nível de invalidação
- Região objetivo
- Evidência histórica
- Acompanhamento
- Encerrado / Invalidado

Avoid unnecessary jargon and never disguise a recommendation merely by renaming it.
## 3. Event classes

HAGMARTK can remain active without forcing a trade event.

1. MARKET_BRIEF — factual market/technology context from verified sources.
2. RADAR — quantitative condition worth monitoring; not yet eligible as a trade-like event.
3. QUANT_EVENT — strategy-defined condition that passed its publication evidence gate.
4. EVENT_UPDATE — deterministic lifecycle update of an existing event.
5. EVENT_AUTOPSY — final factual review of outcome, including failures.
6. RESEARCH_UPDATE — progress/result from strategy research; clearly separated from live evidence.
7. SYSTEM_STATUS — feed quality, engine health or degraded-data warning.

Only QUANT_EVENT may contain a complete reference/invalidation/objective structure.

## 4. Quant Event mandatory fields

A publishable Quant Event must carry, at minimum:
- immutable event_id and strategy_id/version;
- asset, market and timeframe;
- detection and confirmation timestamps in declared time domain;
- lifecycle state;
- factual trigger conditions and their measured values;
- reference region, invalidation level and optional objective regions when defined by strategy;
- evidence provenance: LIVE, SHADOW, BACKTEST or RESEARCH;
- historical sample size and evaluation window when historical statistics are shown;
- cost/fill/data assumptions relevant to the metric;
- machine-readable limitations;
- publication eligibility result and reason;
- short public disclaimer.
## 5. Lifecycle

Canonical lifecycle:
DETECTED -> FORMING -> CONFIRMED -> ACTIVE -> RESOLVED

RESOLVED must contain a terminal reason such as TARGET_REACHED, INVALIDATED, EXPIRED or DATA_INVALID.
Transitions are append-only event facts. Editing history to improve apparent performance is forbidden.

Updates such as objective reached must be generated from the same event object, never as unrelated manual claims.

## 6. Publication gates

A Quant Event is blocked when any mandatory condition fails, including:
- stale/missing/untrusted market data;
- strategy version not registered;
- insufficient evidence under that strategy's declared gate;
- unresolved time-domain or execution-fidelity issue that invalidates the claimed metric;
- missing provenance or sample information;
- metric generated from an unapproved research-only assumption;
- duplicate or contradictory active event for the same strategy contract.

A blocked event may remain visible internally as RADAR/RESEARCH evidence but cannot be promoted as a validated Quant Event.

## 7. Statistics language

Never display a probability, win rate or expectancy without its denominator and provenance.
Prefer: "Em 184 ocorrências comparáveis, 113 atingiram a Região 1 antes da invalidação."
Avoid: "61,4% de chance de ganhar" unless a separately validated probability model truly supports that interpretation.

Backtest, shadow and live observations must never be visually merged into one unlabeled statistic.
## 8. Public disclaimer contract

Short form on every trade-like event:
"Evento quantitativo para estudo e acompanhamento. Não constitui recomendação individual de investimento."

The full publication surface must additionally disclose that markets involve risk, losses are possible, historical/simulated results do not guarantee future performance, and model/data limitations exist.

Disclaimer is not a substitute for compliant product behavior. Before monetized/public trade-like distribution, HAGMARTK requires a dedicated Brazilian regulatory/legal gate.

## 9. Frequency without fabrication

The channel experience must have cadence, but QUANT_EVENT frequency is evidence-driven and has no quota.
During periods without eligible Quant Events, cadence is supplied by MARKET_BRIEF, RADAR, EVENT_UPDATE, EVENT_AUTOPSY, RESEARCH_UPDATE and SYSTEM_STATUS.

A future lower-timeframe strategy may increase genuine event frequency only after passing the same fidelity, robustness and publication gates. Lower timeframe is not permission to weaken evidence standards.

## 10. Broadcast Mode contract

Broadcast Mode is a read-only projection of verified system state for live video.
It may rotate automatically among:
- Visão do Mercado;
- Radar Quantitativo;
- Eventos em acompanhamento;
- Evidências e resultados;
- Laboratório de Estratégias;
- Saúde dos Dados.

It must never fabricate narration, numbers, event states or market activity to keep the screen visually busy.
## 11. Evidence Ledger

Every published Quant Event and lifecycle transition must be retained for later audit.
The ledger must support truthful aggregate reporting, including unsuccessful and invalidated events.
Deletion or selective exclusion for marketing presentation is forbidden except documented data-quality invalidation, which remains auditable.

## 12. Implementation order

1. Define Event schema and lifecycle tests.
2. Build internal Event Engine with no external publishing.
3. Connect one proven strategy in Shadow/read-only mode.
4. Build Evidence Ledger and outcome resolver.
5. Expose Event Radar and event lifecycle in the operational dashboard.
6. Build Broadcast Mode from the same read-only API.
7. Add publication adapters only after security, regulatory and data-quality gates.

No Telegram/Instagram/YouTube adapter may become a second source of truth.