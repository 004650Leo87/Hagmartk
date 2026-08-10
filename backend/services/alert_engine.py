from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.domain.shadow_models import ShadowEvent, ShadowEventType, ShadowState, ShadowTransition
from backend.services.shadow_store import ShadowStoreRepository


class EventPublisher(ABC):
    """Interface abstrata para publicação de eventos no Hagmartk."""

    @abstractmethod
    def publish(self, event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> None:
        pass


class InternalShadowPublisher(EventPublisher):
    """Publicador interno do Shadow Mode.

    ATENÇÃO DE SEGURANÇA CRÍTICA:
    Este publicador atua SOMENTE dentro do repositório/banco SQLite e memória local.
    NENHUMA ordem de broker é enviada.
    NENHUMA mensagem externa (Telegram/WhatsApp/Push) é transmitida.
    """

    def __init__(self, store: ShadowStoreRepository) -> None:
        self.store = store

    def publish(self, event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> None:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Registra a transição de estado no Event Store
        trans_id = f"trans_{event.event_id}_{int(datetime.now(timezone.utc).timestamp())}"
        trans = ShadowTransition(
            transition_id=trans_id,
            event_id=event.event_id,
            from_state=details.get("from_state", "UNKNOWN"),
            to_state=event.current_state,
            timestamp=now_str,
            candle_timestamp=details.get("candle_timestamp", event.market_candle_time),
            market_price=details.get("market_price", event.activation_level),
            reason=details.get("reason", event_type.value),
        )
        self.store.add_transition(trans)


class InternalAlertEngine:
    """Motor de alertas interno do Hagmartk para formatação de cards em Português humanizado."""

    @staticmethod
    def format_market_alert(evt: ShadowEvent) -> Dict[str, Any]:
        """Transforma um ShadowEvent em uma estrutura de alerta humanizada em Português para o painel."""
        dir_pt = "COMPRA" if evt.direction == "BULLISH" else "VENDA"
        pat_pt = evt.pattern_type.replace("_", " ").title()

        state = evt.current_state
        if state == ShadowState.ARMED.value:
            status_pt = "CONFIGURAÇÃO ARMADA"
            desc_pt = f"Aguardando rompimento da região de {evt.activation_level:.4f}."
        elif state == ShadowState.ACTIVATED.value:
            status_pt = "OPORTUNIDADE OBSERVADA (ATIVADA)"
            desc_pt = f"Entrada acionada em {evt.entry_price:.4f}. Acompanhando evolução prospectiva."
        elif state == ShadowState.TARGET_2R.value:
            status_pt = "OBJETIVO 2R ALCANÇADO"
            desc_pt = f"Alvo de 2R em {evt.target_2R:.4f} atingido com sucesso."
        elif state == ShadowState.STOPPED.value:
            status_pt = "STOP ESTRUTURAL ATINGIDO"
            desc_pt = f"Stop estrutural em {evt.initial_stop:.4f} atingido."
        elif state == ShadowState.EXPIRED.value:
            status_pt = "ANÁLISE EXPIRADA"
            desc_pt = "Nível de ativação não foi atingido dentro da janela de 5 candles."
        elif state == ShadowState.INVALIDATED.value:
            status_pt = "ANÁLISE INVALIDADA"
            desc_pt = "Preço violou a máxima/mínima do padrão antes da ativação."
        else:
            status_pt = "ANÁLISE EM FORMAÇÃO"
            desc_pt = "Identificando confluência de divergência de preço/RSI e volume."

        return {
            "alert_id": f"alert_{evt.event_id}",
            "event_id": evt.event_id,
            "title": f"HDF — {evt.symbol} — {evt.timeframe}",
            "subtitle": f"Divergência e Confluência de Mercado ({dir_pt})",
            "direction_label": dir_pt,
            "direction": evt.direction,
            "status_label": status_pt,
            "status_code": evt.current_state,
            "mode": "SHADOW",
            "symbol": evt.symbol,
            "asset_class": evt.asset_class,
            "timeframe": evt.timeframe,
            "pattern": pat_pt,
            "relative_volume": f"{evt.relative_volume:.2f}x",
            "activation_level": evt.activation_level,
            "entry_price": evt.entry_price if evt.entry_price > 0 else None,
            "initial_stop": evt.initial_stop,
            "target_2R": evt.target_2R if evt.target_2R > 0 else None,
            "milestone_1r_reached": evt.milestone_1r_reached,
            "mfe_r_live": evt.mfe_r_live,
            "mae_r_live": evt.mae_r_live,
            "bars_since_activation": evt.bars_since_activation,
            "description": desc_pt,
            "event_time": evt.confluence_time,
            "updated_at": evt.updated_at,
            "is_shadow": True,
            "external_publishing": "DISABLED",
            "broker_trading": "DISABLED",
        }
