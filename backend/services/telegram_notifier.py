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
            self._send_payload("✅ HAGMARTK SHADOW — Telegram conectado\nModo: PAPER / sem ordem real", None, "telegram_test")
        except Exception as exc:
            _logger.warning("[TELEGRAM] test delivery failed error=%s", type(exc).__name__)

    @staticmethod
    def _fmt_price(value: Any) -> str:
        try:
            number = float(value or 0.0)
        except (TypeError, ValueError):
            number = 0.0
        return "—" if number <= 0 else f"{number:.5f}".rstrip("0").rstrip(".")

    @classmethod
    def _format_event_message(cls, event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> str:
        labels = {
            ShadowEventType.SETUP_ARMED: "🟡 CONFIGURAÇÃO ARMADA",
            ShadowEventType.ENTRY_ACTIVATED: "🚀 ENTRADA VIRTUAL ATIVADA",
            ShadowEventType.MILESTONE_1R: "✅ +1R ALCANÇADO",
            ShadowEventType.TARGET_REACHED: "🎯 ALVO 2R ATINGIDO",
            ShadowEventType.STOP_REACHED: "🛑 STOP ESTRUTURAL ATINGIDO",
            ShadowEventType.SETUP_EXPIRED: "⌛ SETUP EXPIRADO",
            ShadowEventType.SETUP_INVALIDATED: "⚪ SETUP INVALIDADO",
        }
        direction = "COMPRA" if str(event.direction).upper() == "BULLISH" else "VENDA"
        lines = [
            f"{labels[event_type]}",
            f"HAGMARTK SHADOW • {event.symbol} • {event.timeframe} • {direction}",
        ]

        if event_type == ShadowEventType.SETUP_ARMED:
            lines.extend([
                f"Ativação: {cls._fmt_price(event.activation_level)}",
                f"Stop: {cls._fmt_price(event.initial_stop)}",
                f"Alvo 2R estimado: {cls._fmt_price(event.target_2R)}",
            ])
        elif event_type == ShadowEventType.ENTRY_ACTIVATED:
            lines.extend([
                f"Entrada: {cls._fmt_price(event.entry_price)}",
                f"Stop: {cls._fmt_price(event.initial_stop)}",
                f"Alvo 2R: {cls._fmt_price(event.target_2R)}",
            ])
        elif event_type == ShadowEventType.MILESTONE_1R:
            lines.append(f"Entrada: {cls._fmt_price(event.entry_price)} • MFE: {float(event.mfe_r_live or 0):.2f}R")
        elif event_type == ShadowEventType.TARGET_REACHED:
            lines.append(f"Resultado: +2.00R • Alvo: {cls._fmt_price(event.target_2R)}")
        elif event_type == ShadowEventType.STOP_REACHED:
            lines.append(f"Resultado: -1.00R • Stop: {cls._fmt_price(event.initial_stop)}")
        else:
            lines.append(f"Motivo: {details.get('reason') or event_type.value}")

        pattern = str(event.pattern_type or "NONE").replace("_", " ")
        if pattern != "NONE":
            lines.append(f"Padrão: {pattern} • Volume: {float(event.relative_volume or 0):.2f}x")
        lines.append(f"Estado: PAPER • ordem real: NÃO")
        lines.append(f"Candle: {details.get('candle_timestamp') or event.market_candle_time or event.confluence_time}")
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
