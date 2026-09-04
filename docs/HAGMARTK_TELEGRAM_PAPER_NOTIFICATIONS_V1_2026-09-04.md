# HAGMARTK — Telegram Paper Notifications V1

Data: 2026-09-04
Escopo: HAGMARTK Shadow / HDF Paper Execution

## Objetivo
Enviar ocorrências operacionais do Paper Execution para Telegram sem habilitar ordens reais no broker.
O canal externo é somente notificação; o MT5 continua leitura de mercado e `real_order_execution_enabled=false`.

## Eventos publicados
- `SETUP_ARMED` — configuração DVP armada.
- `ENTRY_ACTIVATED` — entrada virtual acionada.
- `MILESTONE_1R` — excursão favorável atingiu +1R.
- `TARGET_REACHED` — alvo virtual 2R atingido.
- `STOP_REACHED` — stop estrutural virtual atingido.
- `SETUP_EXPIRED` — não ativou em 5 candles.
- `SETUP_INVALIDATED` — estrutura invalidada antes da entrada.

D, DV e DP permanecem no painel e não são publicados externamente para evitar spam.
## Modelo de mensagem
Cada mensagem contém: estado, ativo, timeframe, direção, entrada/ativação quando aplicável, stop, alvo 2R, padrão, volume, candle e declaração explícita `PAPER • ordem real: NÃO`.

## Transporte suportado
1. `WEBHOOK`: `HAGMARTK_TELEGRAM_WEBHOOK_URL` recebe POST JSON com `text`, `source`, `event_type`, `event_id`.
2. `BOT_API`: `HAGMARTK_TELEGRAM_BOT_TOKEN` + `HAGMARTK_TELEGRAM_CHAT_ID` usam `sendMessage` oficial.

Habilitação: `HAGMARTK_TELEGRAM_ENABLED=1`.
Credenciais ficam somente em `secrets/telegram.env`, diretório ignorado pelo Git.
O status da API nunca retorna URL, token ou chat_id.

## Segurança e confiabilidade
- Telegram não participa da decisão da estratégia.
- Falha de rede não interrompe scanner nem Paper Execution.
- Envio ocorre em thread daemon separada.
- Mesma razão + mesmo candle + mesmo event_id é deduplicada antes do envio.
- Fixtures, synthetic e recovery não geram lifecycle Paper publicável.
- Nenhuma ordem de broker é enviada por esta integração.

## Endpoints
- `GET /api/shadow/notifications/telegram/status`
- `POST /api/shadow/notifications/telegram/test`
