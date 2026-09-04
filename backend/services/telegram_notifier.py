import html
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict

from backend.domain.shadow_models import ShadowEvent, ShadowEventType

_logger = logging.getLogger(__name__)

_ALLOWED_EVENT_TYPES = {
    ShadowEventType.SETUP_ARMED,
    ShadowEventType.ENTRY_ACTIVATED,
    ShadowEventType.MILESTONE_1R,
    ShadowEventType.TARGET_REACHED,
    ShadowEventType.STOP_REACHED,
    ShadowEventType.SETUP_EXPIRED,
    ShadowEventType.SETUP_INVALIDATED,
}


def _env_enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool
    mode: str
    webhook_url: str = ""
    bot_token: str = ""
    chat_id: str = ""
    timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls) -> "TelegramConfig":
        enabled = _env_enabled("HAGMARTK_TELEGRAM_ENABLED")
        webhook = os.getenv("HAGMARTK_TELEGRAM_WEBHOOK_URL", "").strip()
        bot_token = os.getenv("HAGMARTK_TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("HAGMARTK_TELEGRAM_CHAT_ID", "").strip()
        timeout_raw = os.getenv("HAGMARTK_TELEGRAM_TIMEOUT_SECONDS", "5").strip()
        try:
            timeout = max(1.0, min(float(timeout_raw), 15.0))
        except ValueError:
            timeout = 5.0
        mode = "WEBHOOK" if webhook else "BOT_API" if bot_token and chat_id else "CONFIG_MISSING"
        return cls(enabled=enabled, mode=mode, webhook_url=webhook, bot_token=bot_token, chat_id=chat_id, timeout_seconds=timeout)

class TelegramNotifier:
    def __init__(self, config: TelegramConfig | None = None) -> None:
        self.config = config or TelegramConfig.from_environment()

    def status(self) -> Dict[str, Any]:
        configured = self.config.mode in {"WEBHOOK", "BOT_API"}
        return {
            "enabled": self.config.enabled,
            "configured": configured,
            "mode": self.config.mode,
            "ready": bool(self.config.enabled and configured),
            "secrets_exposed": False,
        }

    def notify_async(self, event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> bool:
        if event_type not in _ALLOWED_EVENT_TYPES or not self.status()["ready"]:
            return False
        thread = threading.Thread(
            target=self._safe_send_event,
            args=(event_type, event, dict(details)),
            daemon=True,
            name=f"TelegramNotify-{event.event_id}",
        )
        thread.start()
        return True

    def _safe_send_event(self, event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> None:
        try:
            self._send_payload(self._format_event_message(event_type, event, details), event_type, event.event_id)
        except Exception as exc:
            _logger.warning(
                "[TELEGRAM] delivery failed event_id=%s type=%s error=%s",
                event.event_id,
                event_type.value,
                type(exc).__name__,
            )

    def send_test_async(self) -> bool:
        if not self.status()["ready"]:
            return False
        thread = threading.Thread(
            target=self._safe_send_test,
            daemon=True,
            name="TelegramNotify-Test",
        )
        thread.start()
        return True

    def _safe_send_test(self) -> None:
        try:
            self._send_payload(self._format_test_message(), None, "telegram_test")
        except Exception as exc:
            _logger.warning("[TELEGRAM] test delivery failed error=%s", type(exc).__name__)

    @staticmethod
    def _format_test_message() -> str:
        return (
            "🧪 <b>PRÉVIA DE TEMPLATE — NÃO É EVENTO DE MERCADO</b>\n\n"
            "📡 <b>HAGMARTK SHADOW • DVP</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🟡 <b>CONFIGURAÇÃO ARMADA</b>\n"
            "Possível oportunidade de compra detectada pelo motor.\n\n"
            "📈 <b>MERCADO</b>\n"
            "Ativo: <b>EURUSD</b>\n"
            "Tempo gráfico: <b>M15</b>\n"
            "Direção: <b>▲ COMPRA</b>\n\n"
            "🎯 <b>NÍVEIS OPERACIONAIS</b>\n"
            "Ativação: <code>1.10100</code>\n"
            "Stop estrutural: <code>1.09500</code>\n"
            "Alvo 2R: <code>1.11300</code>\n\n"
            "🧠 <b>CONFLUÊNCIAS DVP</b>\n"
            "✓ Divergência RSI confirmada\n"
            "✓ Volume relativo: <b>1.42x</b>\n"
            "✓ Padrão: <b>Engolfo altista</b>\n\n"
            "🕯 <b>GATILHO VISUAL</b>\n"
            "Candle de compra: <b>BRANCO</b>\n"
            "A imagem técnica será anexada aos eventos quando o renderer estiver ativo.\n\n"
            "🛡 <b>CONTROLE OPERACIONAL</b>\n"
            "Modo: <b>SHADOW / PAPER</b>\n"
            "Ordem real: <b>NÃO</b>\n\n"
            "🕒 <b>REGISTRO</b>\n"
            "Evento demonstrativo para validação visual do Telegram."
        )

    @staticmethod
    def _fmt_price(value: Any) -> str:
        try:
            number = float(value or 0.0)
        except (TypeError, ValueError):
            number = 0.0
        return "—" if number <= 0 else f"{number:.5f}".rstrip("0").rstrip(".")

    @staticmethod
    def _esc(value: Any) -> str:
        return html.escape(str(value or ""), quote=False)

    @staticmethod
    def _human_pattern(value: Any) -> str:
        raw = str(value or "NONE").replace("_", " ").strip()
        if not raw or raw.upper() == "NONE":
            return "Não informado"
        return raw.title()

    @classmethod
    def _format_event_message(cls, event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> str:
        labels = {
            ShadowEventType.SETUP_ARMED: ("🟡", "CONFIGURAÇÃO ARMADA"),
            ShadowEventType.ENTRY_ACTIVATED: ("⚡", "ENTRADA VIRTUAL ATIVADA"),
            ShadowEventType.MILESTONE_1R: ("✅", "+1R ALCANÇADO"),
            ShadowEventType.TARGET_REACHED: ("🎯", "ALVO 2R ATINGIDO"),
            ShadowEventType.STOP_REACHED: ("🛑", "STOP ESTRUTURAL ATINGIDO"),
            ShadowEventType.SETUP_EXPIRED: ("⌛", "SETUP EXPIRADO"),
            ShadowEventType.SETUP_INVALIDATED: ("⚪", "SETUP INVALIDADO"),
        }
        icon, label = labels[event_type]
        direction = "COMPRA" if str(event.direction).upper() == "BULLISH" else "VENDA"
        direction_icon = "▲" if direction == "COMPRA" else "▼"
        trigger_color = "BRANCO" if direction == "COMPRA" else "AMARELO"
        candle_time = details.get("candle_timestamp") or event.market_candle_time or event.confluence_time or "—"
        pattern = cls._human_pattern(event.pattern_type)

        lines = [
            "📡 <b>HAGMARTK SHADOW • DVP</b>",
            "━━━━━━━━━━━━━━━━━━",
            "",
            f"{icon} <b>{label}</b>",
            "",
            "📈 <b>MERCADO</b>",
            f"Ativo: <b>{cls._esc(event.symbol)}</b>",
            f"Tempo gráfico: <b>{cls._esc(event.timeframe)}</b>",
            f"Direção: <b>{direction_icon} {direction}</b>",
            "",
        ]

        if event_type in {ShadowEventType.SETUP_ARMED, ShadowEventType.ENTRY_ACTIVATED}:
            lines.extend([
                "🎯 <b>NÍVEIS OPERACIONAIS</b>",
                f"Ativação: <code>{cls._fmt_price(event.activation_level)}</code>",
                f"Entrada virtual: <code>{cls._fmt_price(event.entry_price)}</code>",
                f"Stop estrutural: <code>{cls._fmt_price(event.initial_stop)}</code>",
                f"Alvo 2R: <code>{cls._fmt_price(event.target_2R)}</code>",
                "",
                "🧠 <b>CONFLUÊNCIAS DVP</b>",
                "✓ Divergência RSI confirmada",
                f"✓ Volume relativo: <b>{float(event.relative_volume or 0):.2f}x</b>",
                f"✓ Padrão de candle: <b>{cls._esc(pattern)}</b>",
                "",
                "🕯 <b>GATILHO VISUAL</b>",
                f"Candle de {direction.lower()}: <b>{trigger_color}</b>",
                "",
            ])
        elif event_type == ShadowEventType.MILESTONE_1R:
            lines.extend([
                "📊 <b>EVOLUÇÃO</b>",
                f"Entrada virtual: <code>{cls._fmt_price(event.entry_price)}</code>",
                f"MFE atual: <b>+{float(event.mfe_r_live or 0):.2f}R</b>",
                f"MAE atual: <b>{float(event.mae_r_live or 0):.2f}R</b>",
                f"Candles desde ativação: <b>{int(event.bars_since_activation or 0)}</b>",
                "",
            ])
        elif event_type in {ShadowEventType.TARGET_REACHED, ShadowEventType.STOP_REACHED}:
            result = "+2.00R" if event_type == ShadowEventType.TARGET_REACHED else "-1.00R"
            exit_label = "Alvo 2R" if event_type == ShadowEventType.TARGET_REACHED else "Stop"
            exit_value = event.target_2R if event_type == ShadowEventType.TARGET_REACHED else event.initial_stop
            lines.extend([
                "💰 <b>FECHAMENTO TÉCNICO</b>",
                f"Entrada virtual: <code>{cls._fmt_price(event.entry_price)}</code>",
                f"{exit_label}: <code>{cls._fmt_price(exit_value)}</code>",
                f"Resultado bruto: <b>{result}</b>",
                f"Candles desde ativação: <b>{int(event.bars_since_activation or 0)}</b>",
                "",
            ])
        else:
            reason = cls._esc(details.get("reason") or event_type.value)
            lines.extend([
                "📋 <b>ENCERRAMENTO</b>",
                f"Motivo: {reason}",
                "",
            ])

        lines.extend([
            "🛡 <b>CONTROLE OPERACIONAL</b>",
            "Modo: <b>SHADOW / PAPER</b>",
            "Ordem real: <b>NÃO</b>",
            "",
            "🕒 <b>REGISTRO</b>",
            f"Candle/evento: <code>{cls._esc(candle_time)}</code>",
        ])
        return "\n".join(lines)

    def _send_payload(self, text: str, event_type: ShadowEventType | None, event_id: str) -> None:
        if self.config.mode == "WEBHOOK":
            url = self.config.webhook_url
            payload = {
                "text": text,
                "source": "HAGMARTK_SHADOW_PAPER",
                "event_type": event_type.value if event_type else "TEST",
                "event_id": event_id,
            }
        elif self.config.mode == "BOT_API":
            url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
            payload = {
                "chat_id": self.config.chat_id,
                "text": text,
                "disable_web_page_preview": True,
                "parse_mode": "HTML",
            }
        else:
            raise RuntimeError("Telegram configuration is incomplete")

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            if not 200 <= int(response.status) < 300:
                raise RuntimeError(f"Telegram HTTP {response.status}")
            if self.config.mode == "BOT_API":
                data = json.loads(response.read().decode("utf-8") or "{}")
                if not data.get("ok", False):
                    raise RuntimeError("Telegram Bot API returned ok=false")
