import html
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import requests
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from backend.domain.shadow_models import ShadowEvent, ShadowEventType
from backend.services.market_alert_image import render_market_alert_chart
from backend.services.telegram_thread_store import TelegramThreadStore
from backend.services.telegram_publication_policy import (
    evaluate_dvp_root, evaluate_orb_root,
)
from backend.services.orb_publication_policy import (
    OrbPublicationConfig, evaluate_orb_publication,
)
from backend.services.market_alert_template import (
    build_cycle_alert, build_dvp_alert, build_orb_alert, format_telegram_alert,
)

_logger = logging.getLogger(__name__)

_TELEGRAM_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="TelegramDispatch")
_TELEGRAM_RATE_LOCK = threading.Lock()
_TELEGRAM_LAST_SEND = 0.0
_TELEGRAM_MIN_INTERVAL = 1.05


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
    def __init__(self, config: TelegramConfig | None = None, thread_store: TelegramThreadStore | None = None) -> None:
        self.config = config or TelegramConfig.from_environment()
        self.thread_store = thread_store or TelegramThreadStore()
        self.market_adapter = None
        self.orb_publication_config = OrbPublicationConfig.from_environment()

    def status(self) -> Dict[str, Any]:
        configured = self.config.mode in {"WEBHOOK", "BOT_API"}
        return {
            "enabled": self.config.enabled,
            "configured": configured,
            "mode": self.config.mode,
            "ready": bool(self.config.enabled and configured),
            "secrets_exposed": False,
        }

    def _telegram_post(self, url: str, **kwargs: Any) -> requests.Response:
        response = None
        for attempt in range(3):
            self._wait_telegram_slot()
            response = requests.post(url, **kwargs)
            if response.status_code != 429:
                return response
            if attempt >= 2:
                return response
            retry_after = _TELEGRAM_MIN_INTERVAL
            try:
                body = response.json()
                retry_after = max(float((body.get("parameters") or {}).get("retry_after") or retry_after), _TELEGRAM_MIN_INTERVAL)
            except Exception:
                retry_after = max(retry_after, 1.0)
            time.sleep(retry_after)
        return response

    @classmethod
    def _format_orb_message(cls, event_type: str, event: Dict[str, Any]) -> str:
        labels = {
            "SIGNAL": "SINAL ORB CONFIRMADO",
            "ENTRY_FILLED": "ENTRADA PAPER ATIVADA",
            "ENTRY_REJECTED": "ENTRADA PAPER REJEITADA",
            "EXIT_FILLED": "OPERACAO PAPER ENCERRADA",
        }
        direction = str(event.get("direction") or "-").upper()
        lines = [
            "<b>HAGMARTK SHADOW - ORB</b>",
            "------------------",
            f"<b>{cls._esc(labels.get(event_type, event_type))}</b>",
            f"Ativo: <b>{cls._esc(event.get('symbol'))}</b>",
            f"Direcao: <b>{cls._esc(direction)}</b>",
        ]
        for label, key in (("H_OR", "H_OR"), ("L_OR", "L_OR"), ("Entrada", "entry"), ("Stop", "stop"), ("Alvo 2R", "target")):
            if event.get(key) not in (None, ""):
                lines.append(f"{label}: <code>{cls._esc(event.get(key))}</code>")
        if event.get("exit_reason"):
            lines.append(f"Saida: <b>{cls._esc(event.get('exit_reason'))}</b>")
        if event.get("r_multiple") not in (None, ""):
            lines.append(f"Resultado: <b>{cls._esc(event.get('r_multiple'))}R</b>")
        if event.get("reason"):
            lines.append(f"Motivo: {cls._esc(event.get('reason'))}")
        lines.extend([
            "Modo: <b>SHADOW / PAPER</b>",
            "Ordem real: <b>NAO</b>",
        ])
        return "\n".join(lines)

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
            "🧪 <b>PRÉVIA DO NOVO PADRÃO — NÃO É EVENTO DE MERCADO</b>\n\n"
            "🟢 <b>HAGMARTK DVP</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<b>OPERAÇÃO REGISTRADA</b>\n\n"
            "📌 <b>Ativo:</b> EURUSD\n"
            "🕒 <b>Horário (Brasília):</b> 08/09/2026 • 16:05:00\n"
            "🟢 <b>Direção:</b> COMPRA\n"
            "⏱️ <b>Gráfico:</b> M5\n\n"
            "🎯 <b>Níveis da operação</b>\n"
            "Entrada: <code>1.10100</code>\n"
            "🛑 Stop: <code>1.09500</code>\n"
            "🎯 Alvo 2R: <code>1.11300</code>\n\n"
            "🧪 <b>Acompanhamento:</b> Shadow / Simulação\n"
            "🔒 Nenhuma ordem real foi enviada."
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

    @classmethod
    def _format_cycle_message(cls, event: Dict[str, Any]) -> str:
        labels = {
            "CHANNEL_DEFINED": ("??", "CANAL DO CICLO DEFINIDO"),
            "EXPANSION_WAIT_BUY": ("??", "EXPANS?O APONTA COMPRA"),
            "EXPANSION_WAIT_SELL": ("??", "EXPANS?O APONTA VENDA"),
            "SETUP_REVERSED": ("??", "INVERS?O DO CICLO"),
            "EXPANSION_CONFIRMED": ("?", "EXPANS?O CONFIRMADA"),
            "ORDER_SUBMITTED": ("??", "ORDEM PAPER GERADA"),
            "LIMIT_FILLED": ("?", "ENTRADA PAPER ATIVADA"),
            "PARTIAL_EXECUTED": ("??", "PARCIAL REALIZADA"),
            "BREAKEVEN_APPLIED": ("??", "BREAKEVEN APLICADO"),
            "TARGET_LEVEL_REACHED": ("??", "ALVO DO CICLO ATINGIDO"),
            "TAKE_PROFIT": ("??", "ALVO FINAL ATINGIDO"),
            "STOP_LOSS": ("??", "STOP DO CICLO ATINGIDO"),
            "POSITION_CLOSED": ("??", "OPERA??O PAPER ENCERRADA"),
            "PULLBACK_MISSED": ("?", "PULLBACK PERDIDO"),
        }
        event_type = str(event.get("event_type") or "CYCLE_EVENT")
        icon, label = labels.get(event_type, ("??", event_type.replace("_", " ")))
        direction = str(event.get("direction") or "NEUTRO").upper()
        direction_label = {"BUY": "? COMPRA", "SELL": "? VENDA", "NEUTRO": "?"}.get(direction, direction)
        levels = event.get("levels") or {}
        payload = event.get("payload") or {}
        lines = [
            "?? <b>HAGMARTK SHADOW ? TEORIA DOS CICLOS V111</b>",
            "??????????????????",
            "",
            f"{icon} <b>{cls._esc(label)}</b>",
            "",
            "?? <b>MERCADO</b>",
            f"Ativo: <b>{cls._esc(event.get('symbol'))}</b>",
            f"Tempo gr?fico: <b>{cls._esc(event.get('timeframe'))}</b>",
            f"Dire??o: <b>{cls._esc(direction_label)}</b>",
            "",
            "?? <b>ESTRUTURA DO CICLO</b>",
            f"Canal superior: <code>{cls._fmt_price(levels.get('channel_high'))}</code>",
            f"Canal inferior: <code>{cls._fmt_price(levels.get('channel_low'))}</code>",
            f"N?vel de expans?o: <code>{cls._fmt_price(levels.get('expansion'))}</code>",
            "",
        ]
        if any(levels.get(k) for k in ("entry", "stop", "target_1", "target_2", "target_3")):
            lines.extend([
                "?? <b>N?VEIS PAPER</b>",
                f"Entrada: <code>{cls._fmt_price(levels.get('entry'))}</code>",
                f"Stop: <code>{cls._fmt_price(levels.get('stop'))}</code>",
                f"Alvo 1: <code>{cls._fmt_price(levels.get('target_1'))}</code>",
                f"Alvo 2: <code>{cls._fmt_price(levels.get('target_2'))}</code>",
                f"Alvo 3: <code>{cls._fmt_price(levels.get('target_3'))}</code>",
                "",
            ])
        detail = payload.get("detail") or payload.get("reason")
        if detail:
            lines.extend(["?? <b>LEITURA DO MOTOR</b>", cls._esc(detail), ""])
        lines.extend([
            "?? <b>VALIDA??O PROSPECTIVA</b>",
            "Fonte: <b>mercado real / MT5</b>",
            "Execu??o: <b>SHADOW / PAPER</b>",
            "Ordem real: <b>N?O</b>",
            "Probabilidade de alvo: <b>n?o calibrada</b>",
            "",
            "?? <b>REGISTRO</b>",
            f"Evento: <code>{cls._esc(event.get('event_time'))}</code>",
        ])
        return "\n".join(lines)

    def _send_payload(
        self, text: str, event_type: Any, event_id: str, source: str = "HAGMARTK_SHADOW_PAPER"
    ) -> None:
        if self.config.mode == "WEBHOOK":
            url = self.config.webhook_url
            payload = {
                "text": text,
                "source": source,
                "event_type": (event_type.value if hasattr(event_type, "value") else str(event_type or "TEST")),
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

    # Unified HAGMARTK notification pipeline (latest definitions override legacy helpers above).
    def set_market_adapter(self, adapter: Any) -> None:
        self.market_adapter = adapter

    def _load_candles(self, alert: Dict[str, Any]) -> list[Dict[str, Any]]:
        if self.market_adapter is None:
            return []
        try:
            rows = self.market_adapter.get_candles(
                alert.get("symbol"), alert.get("timeframe") or "M5", count=100
            )
            return list(rows or [])
        except Exception:
            return []

    @classmethod
    def _format_event_message(cls, event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> str:
        return format_telegram_alert(build_dvp_alert(event_type, event, details))

    @classmethod
    def _format_cycle_message(cls, event: Dict[str, Any]) -> str:
        return format_telegram_alert(build_cycle_alert(event))

    @classmethod
    def _format_orb_message(cls, event_type: str, event: Dict[str, Any]) -> str:
        return format_telegram_alert(build_orb_alert(event_type, event))
    def _deliver_alert(
        self,
        alert: Dict[str, Any],
        event_type: Any,
        event_id: str,
        operation_key: str,
        source: str,
        root: bool,
        closed: bool = False,
    ) -> None:
        root_row = self.thread_store.get(operation_key)
        if not root and root_row is None:
            _logger.info("[TELEGRAM] suppressed orphan update operation=%s event=%s", operation_key, event_id)
            return
        reply_id = None if root else root_row.get("root_message_id")
        image_png = None
        if root:
            candles = self._load_candles(alert)
            if candles:
                try:
                    image_png = render_market_alert_chart(
                        alert, candles, alert.get("evidence") or {}
                    )
                except Exception:
                    image_png = None
        message_id = self._send_payload(
            format_telegram_alert(alert), event_type, event_id,
            source=source, reply_to_message_id=reply_id, image_png=image_png,
        )
        if root and message_id:
            self.thread_store.set_root(
                operation_key,
                alert.get("strategy_key") or source,
                self.config.chat_id,
                message_id,
                event_id,
            )
            if source == "HAGMARTK_ORB_SHADOW":
                self.thread_store.mark_publication_status("ORB", event_id, "PUBLISHED")
        if closed and root_row:
            self.thread_store.close(operation_key)

    def _safe_send_event(
        self,
        event_type: ShadowEventType,
        event: ShadowEvent,
        details: Dict[str, Any],
    ) -> None:
        try:
            alert = build_dvp_alert(event_type, event, details)
            alert["evidence"] = dict(event.evidence or {})
            root = event_type == ShadowEventType.ENTRY_ACTIVATED
            closed = event_type in {
                ShadowEventType.TARGET_REACHED,
                ShadowEventType.STOP_REACHED,
                ShadowEventType.SETUP_EXPIRED,
                ShadowEventType.SETUP_INVALIDATED,
            }
            self._deliver_alert(
                alert,
                event_type,
                event.event_id,
                f"DVP:{event.event_id}",
                "HAGMARTK_SHADOW_PAPER",
                root,
                closed,
            )
        except Exception as exc:
            _logger.warning(
                "[TELEGRAM] delivery failed event_id=%s type=%s error=%s",
                event.event_id,
                event_type.value,
                type(exc).__name__,
            )

    def _safe_send_cycle(self, event: Dict[str, Any]) -> None:
        try:
            alert = build_cycle_alert(event)
            alert["evidence"] = dict(event.get("levels") or {})
            event_type = str(event.get("event_type") or "CYCLE_EVENT")
            payload = event.get("payload") or {}
            operation_id = str(payload.get("operation_id") or event.get("event_id"))
            root = event_type in {"LIMIT_FILLED", "POSITION_OPENED"}
            closed = event_type in {
                "TAKE_PROFIT", "STOP_LOSS", "POSITION_CLOSED", "PULLBACK_MISSED"
            }
            self._deliver_alert(
                alert,
                event_type,
                str(event.get("event_id") or operation_id),
                f"TC:{operation_id}",
                "HAGMARTK_CYCLE_THEORY_SHADOW",
                root,
                closed,
            )
        except Exception as exc:
            _logger.warning(
                "[TELEGRAM] Cycle Theory delivery failed event_id=%s error=%s",
                event.get("event_id"),
                type(exc).__name__,
            )

    def _safe_send_orb(self, event_type: str, event: Dict[str, Any]) -> None:
        try:
            alert = build_orb_alert(event_type, event)
            alert["evidence"] = {
                "range_high": event.get("range_high"),
                "range_low": event.get("range_low"),
                "t0": event.get("t0"),
                "signal_time": event.get("signal_time"),
            }
            operation_id = str(
                event.get("session_id") or event.get("signal_id") or "orb"
            )
            root = event_type == "ENTRY_FILLED"
            closed = event_type in {
                "EXIT_FILLED", "EXIT_UNRESOLVED", "ENTRY_REJECTED"
            }
            self._deliver_alert(
                alert,
                event_type,
                str(event.get("signal_id") or operation_id),
                f"ORB:{operation_id}",
                "HAGMARTK_ORB_SHADOW",
                root,
                closed,
            )
        except Exception as exc:
            if event_type == "ENTRY_FILLED":
                signal_id = str(event.get("signal_id") or "orb_event")
                self.thread_store.mark_publication_status("ORB", signal_id, "FAILED")
            _logger.warning(
                "[TELEGRAM] ORB delivery failed event=%s error=%s",
                event_type,
                type(exc).__name__,
            )

    def _send_payload(
        self,
        text: str,
        event_type: Any,
        event_id: str,
        source: str = "HAGMARTK_SHADOW_PAPER",
        reply_to_message_id: int | None = None,
        image_png: bytes | None = None,
    ) -> int | None:
        if self.config.mode == "WEBHOOK":
            payload = {
                "text": text,
                "source": source,
                "event_type": (
                    event_type.value if hasattr(event_type, "value")
                    else str(event_type or "TEST")
                ),
                "event_id": event_id,
            }
            if reply_to_message_id:
                payload["reply_to_message_id"] = int(reply_to_message_id)
            response = requests.post(
                self.config.webhook_url,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            return None

        if self.config.mode != "BOT_API":
            raise RuntimeError("Telegram configuration is incomplete")

        base = f"https://api.telegram.org/bot{self.config.bot_token}"
        if image_png:
            data = {
                "chat_id": self.config.chat_id,
                "parse_mode": "HTML",
                "caption": text,
            }
            if reply_to_message_id:
                data["reply_parameters"] = json.dumps(
                    {"message_id": int(reply_to_message_id)}
                )
            response = self._telegram_post(
                base + "/sendPhoto",
                data=data,
                files={
                    "photo": (
                        "hagmartk-evidence.png",
                        image_png,
                        "image/png",
                    )
                },
                timeout=self.config.timeout_seconds,
            )
        else:
            payload = {
                "chat_id": self.config.chat_id,
                "text": text,
                "disable_web_page_preview": True,
                "parse_mode": "HTML",
            }
            if reply_to_message_id:
                payload["reply_parameters"] = {
                    "message_id": int(reply_to_message_id)
                }
            response = self._telegram_post(
                base + "/sendMessage",
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok", False):
            raise RuntimeError("Telegram Bot API returned ok=false")
        message = result.get("result") or {}
        message_id = message.get("message_id")
        return int(message_id) if message_id is not None else None

    @staticmethod
    def _format_test_message() -> str:
        preview = {
            "symbol": "BTCUSDT",
            "event_time": "2026-09-09T20:45:00+00:00",
            "direction": "LONG",
            "entry": "108450",
            "stop": "108090",
            "target": "109120",
        }
        return format_telegram_alert(build_orb_alert("ENTRY_FILLED", preview))

    def _wait_telegram_slot(self) -> None:
        global _TELEGRAM_LAST_SEND
        with _TELEGRAM_RATE_LOCK:
            now = time.monotonic()
            wait = _TELEGRAM_MIN_INTERVAL - (now - _TELEGRAM_LAST_SEND)
            if wait > 0:
                time.sleep(wait)
            _TELEGRAM_LAST_SEND = time.monotonic()

    def notify_async(self, event_type: ShadowEventType, event: ShadowEvent, details: Dict[str, Any]) -> bool:
        allowed = {
            ShadowEventType.ENTRY_ACTIVATED,
            ShadowEventType.MILESTONE_1R,
            ShadowEventType.TARGET_REACHED,
            ShadowEventType.STOP_REACHED,
        }
        if event_type not in allowed or not self.status()["ready"]:
            return False
        if event_type == ShadowEventType.ENTRY_ACTIVATED:
            decision = evaluate_dvp_root(event)
            if not decision.allowed:
                _logger.info("[TELEGRAM] DVP root suppressed event=%s reason=%s", event.event_id, decision.reason)
                return False
        _TELEGRAM_EXECUTOR.submit(self._safe_send_event, event_type, event, dict(details))
        return True

    def notify_cycle_async(self, event: Dict[str, Any]) -> bool:
        if not self.status()["ready"]:
            return False
        _TELEGRAM_EXECUTOR.submit(self._safe_send_cycle, dict(event))
        return True

    def notify_orb_async(self, event_type: str, event: Dict[str, Any]) -> bool:
        allowed = {"ENTRY_FILLED", "EXIT_FILLED", "EXIT_UNRESOLVED"}
        if event_type not in allowed or not self.status()["ready"]:
            return False
        if event_type == "ENTRY_FILLED":
            signal_id = str(event.get("signal_id") or "orb_event")
            session_id = str(event.get("session_id") or signal_id)
            operation_key = f"ORB:{session_id}"
            symbol = str(event.get("symbol") or "").upper()
            root_decision = evaluate_orb_root(event)
            if not root_decision.allowed:
                self.thread_store.record_suppression(
                    "ORB", signal_id, operation_key, symbol, 0.0, root_decision.reason,
                )
                _logger.info("[TELEGRAM] ORB root suppressed signal=%s reason=%s", signal_id, root_decision.reason)
                return False
            now = datetime.now(timezone.utc)
            since = now - timedelta(minutes=self.orb_publication_config.lookback_minutes)
            recent = self.thread_store.recent_publication_activity("ORB", since.isoformat())
            decision = evaluate_orb_publication(
                event, recent, now=now, config=self.orb_publication_config,
            )
            if not decision.allowed:
                self.thread_store.record_suppression(
                    "ORB", signal_id, operation_key, symbol, decision.score, decision.reason,
                )
                _logger.info(
                    "[TELEGRAM] ORB publication suppressed signal=%s reason=%s score=%.2f",
                    signal_id, decision.reason, decision.score,
                )
                return False
            if not self.thread_store.reserve_publication(
                "ORB", signal_id, operation_key, symbol, decision.score, decision.reason,
            ):
                _logger.info("[TELEGRAM] ORB duplicate reservation signal=%s", signal_id)
                return False
            event = dict(event)
            event["publication_score"] = decision.score
        _TELEGRAM_EXECUTOR.submit(self._safe_send_orb, str(event_type), dict(event))
        return True

    def send_test_async(self) -> bool:
        if not self.status()["ready"]:
            return False
        _TELEGRAM_EXECUTOR.submit(self._safe_send_test)
        return True
