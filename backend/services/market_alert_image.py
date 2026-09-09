from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

_BG = "#071017"
_GRID = "#1c2a34"
_TEXT = "#edf2f7"
_MUTED = "#8f9ca8"
_GOLD = "#d5a847"
_GREEN = "#31d887"
_RED = "#ff565d"
_BLUE = "#55b6ff"
_WHITE = "#f7f9fb"
_YELLOW = "#ffd84d"


def _font(size: int, bold: bool = False):
    paths = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()
def _parse_time(value: Any) -> float:
    if isinstance(value, datetime):
        dt = value
    elif value:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return 0.0
    else:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).timestamp()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _price(value: float) -> str:
    absolute = abs(value)
    if absolute >= 10000:
        places = 2
    elif absolute >= 100:
        places = 3
    elif absolute >= 1:
        places = 5
    elif absolute >= 0.01:
        places = 6
    else:
        places = 8
    return f"{value:.{places}f}".rstrip("0").rstrip(".")
def _normalize_candles(rows: Iterable[dict[str, Any]]) -> list[dict[str, float]]:
    result: list[dict[str, float]] = []
    for row in rows or []:
        try:
            ts = _parse_time(row.get("time") or row.get("open_time"))
            item = {
                "time": ts,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume") or row.get("tick_volume") or 0.0),
            }
        except (KeyError, TypeError, ValueError):
            continue
        if ts > 0 and item["high"] >= item["low"]:
            result.append(item)
    result.sort(key=lambda item: item["time"])
    return result[-72:]


def _draw_hm(image: Image.Image, draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float = 1.0) -> None:
    size = max(30, int(82 * scale))
    logo_path = Path(__file__).resolve().parents[1] / "assets" / "hm-logo.png"
    try:
        logo = Image.open(logo_path).convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
        image.paste(logo, (int(cx - size / 2), int(cy - size / 2)), mask)
        return
    except Exception:
        pass
    radius = int(35 * scale)
    draw.arc((cx-radius, cy-radius, cx+radius, cy+radius), 195, 350, fill=_GOLD, width=max(2, int(3*scale)))
    draw.arc((cx-radius, cy-radius, cx+radius, cy+radius), 15, 165, fill=_GOLD, width=max(2, int(3*scale)))
    f = _font(max(12, int(30 * scale)), bold=True)
    draw.text((cx-radius+8*scale, cy-18*scale), "H", fill="#c7cbd1", font=f)
    draw.text((cx-2*scale, cy-18*scale), "M", fill=_GOLD, font=f)

def _nearest_index(candles: list[dict[str, float]], value: Any) -> int:
    ts = _parse_time(value)
    if not candles or not ts:
        return len(candles) - 1
    return min(range(len(candles)), key=lambda i: abs(candles[i]["time"] - ts))


def _levels(alert: dict[str, Any]) -> list[tuple[str, float, str]]:
    rows: list[tuple[str, float, str]] = []
    entry = _num(alert.get("entry"))
    if entry:
        rows.append(("Entrada", entry, _WHITE))
    for target in alert.get("targets") or []:
        value = _num(target.get("value"))
        if value:
            rows.append((str(target.get("label") or "Alvo"), value, _GREEN))
    stop = _num(alert.get("stop"))
    if stop:
        rows.append(("Stop", stop, _RED))
    return rows


def render_market_alert_chart(
    alert: dict[str, Any],
    candles_rows: Iterable[dict[str, Any]],
    evidence: dict[str, Any] | None = None,
) -> bytes | None:
    candles = _normalize_candles(candles_rows)
    if len(candles) < 8:
        return None
    evidence = dict(evidence or alert.get("evidence") or {})
    width, height = 1280, 720
    image = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(image)
    chart_left, chart_top = 62, 112
    chart_right, chart_bottom = 1110, 630
    chart_w = chart_right - chart_left
    chart_h = chart_bottom - chart_top

    strategy = str(alert.get("strategy") or alert.get("strategy_name") or "HAGMARTK")
    symbol = str(alert.get("symbol") or "—")
    timeframe = str(alert.get("timeframe") or "M5")
    _draw_hm(image, draw, 54, 50, 0.72)
    draw.text((96, 25), strategy, fill=_TEXT, font=_font(28, True))
    draw.text((96, 62), f"{symbol} · {timeframe} · EVIDÊNCIA SHADOW", fill=_MUTED, font=_font(17))
    draw.line((62, 94, width - 62, 94), fill="#25333d", width=1)

    levels = _levels(alert)
    extra_prices = [value for _, value, _ in levels]
    for key in ("channel_high", "channel_low", "expansion", "c1_mid", "mid_line50", "range_high", "range_low"):
        value = _num(evidence.get(key))
        if value:
            extra_prices.append(value)
    lows = [row["low"] for row in candles] + extra_prices
    highs = [row["high"] for row in candles] + extra_prices
    lo, hi = min(lows), max(highs)
    span = max(hi - lo, abs(hi) * 0.001, 1e-9)
    lo -= span * 0.10
    hi += span * 0.10

    def y(price: float) -> float:
        return chart_top + ((hi - price) / (hi - lo)) * chart_h

    step = chart_w / max(len(candles), 1)
    def x(index: int) -> float:
        return chart_left + step * index + step / 2
    draw.rounded_rectangle((chart_left, chart_top, chart_right, chart_bottom), radius=12, outline="#24323c", width=2, fill="#08131b")
    for i in range(6):
        yy = chart_top + chart_h * i / 5
        price = hi - (hi - lo) * i / 5
        draw.line((chart_left, yy, chart_right, yy), fill=_GRID, width=1)
        draw.text((chart_right + 12, yy - 8), _price(price), fill=_MUTED, font=_font(13))
    for i in range(7):
        idx = min(len(candles) - 1, round((len(candles) - 1) * i / 6))
        xx = x(idx)
        draw.line((xx, chart_top, xx, chart_bottom), fill="#14222c", width=1)
        label = datetime.fromtimestamp(candles[idx]["time"], tz=timezone.utc).astimezone().strftime("%H:%M")
        draw.text((xx - 20, chart_bottom + 10), label, fill=_MUTED, font=_font(12))

    watermark_font = _font(72, True)
    draw.text((420, 300), "HAGMARTK", fill="#13232d", font=watermark_font)
    _draw_hm(image, draw, 1190, 57, 0.65)

    event_idx = _nearest_index(candles, alert.get("event_time_utc") or alert.get("event_time"))
    body_w = max(3, int(step * 0.58))
    max_vol = max((row.get("volume", 0.0) for row in candles), default=0.0)
    for idx, candle in enumerate(candles):
        xx = x(idx)
        up = candle["close"] >= candle["open"]
        color = _GREEN if up else _RED
        if str(alert.get("strategy_key")) == "DVP" and idx == event_idx:
            color = _WHITE if str(alert.get("direction")) == "COMPRA" else _YELLOW
        draw.line((xx, y(candle["high"]), xx, y(candle["low"])), fill=color, width=2)
        top = min(y(candle["open"]), y(candle["close"]))
        bottom = max(y(candle["open"]), y(candle["close"]))
        draw.rectangle((xx-body_w/2, top, xx+body_w/2, max(top+2, bottom)), fill=color)
        if max_vol > 0 and candle.get("volume", 0.0) > 0:
            vh = 48 * candle["volume"] / max_vol
            draw.rectangle((xx-body_w/2, chart_bottom-vh, xx+body_w/2, chart_bottom), fill="#167e61" if up else "#73363c")
    strategy_key = str(alert.get("strategy_key") or "")
    ref_idx = _nearest_index(candles, evidence.get("ref_time_start"))

    if strategy_key == "TC":
        ch_high = _num(evidence.get("channel_high"))
        ch_low = _num(evidence.get("channel_low"))
        if ch_high and ch_low:
            left_x = x(ref_idx if ref_idx >= 0 else max(0, event_idx - 18))
            right_x = x(event_idx)
            draw.rectangle((left_x, y(ch_high), right_x, y(ch_low)), fill="#111d25", outline="#c5ced7", width=2)
            mid_y = (y(ch_high) + y(ch_low)) / 2
            draw.text((left_x + 12, mid_y - 24), "ZONA NEUTRA", fill=_TEXT, font=_font(15, True))
            draw.text((left_x + 12, mid_y + 2), "CANAL NEUTRO", fill=_MUTED, font=_font(13))
        c1_mid = _num(evidence.get("c1_mid"))
        if c1_mid:
            draw.line((x(max(0, ref_idx)), y(c1_mid), x(event_idx), y(c1_mid)), fill=_GOLD, width=2)
            draw.text((x(max(0, ref_idx)) + 6, y(c1_mid) - 24), "C1", fill=_GOLD, font=_font(16, True))
        split_mid = _num(evidence.get("mid_line50"))
        if split_mid and evidence.get("is_split_active"):
            draw.line((x(max(0, ref_idx)), y(split_mid), x(event_idx), y(split_mid)), fill=_YELLOW, width=1)
            draw.text((x(event_idx) - 110, y(split_mid) - 20), "DIVISÃO 50%", fill=_YELLOW, font=_font(12, True))
        expansion = _num(evidence.get("expansion"))
        if expansion:
            draw.line((x(max(0, event_idx - 4)), y(expansion), chart_right, y(expansion)), fill=_GOLD, width=3)
            draw.text((chart_right - 170, y(expansion) - 24), "EXPANSÃO", fill=_GOLD, font=_font(14, True))
    if strategy_key == "ORB":
        range_high = _num(evidence.get("range_high"))
        range_low = _num(evidence.get("range_low"))
        t0_idx = _nearest_index(candles, evidence.get("t0"))
        signal_idx = _nearest_index(candles, evidence.get("signal_time") or alert.get("event_time_utc"))
        if range_high and range_low:
            left_x = x(t0_idx if t0_idx >= 0 else max(0, signal_idx - 12))
            right_x = x(signal_idx)
            draw.rectangle((left_x, y(range_high), right_x, y(range_low)), fill="#0c2940", outline=_BLUE, width=2)
            draw.text((left_x + 12, (y(range_high) + y(range_low))/2 - 8), "OPENING RANGE", fill="#91ceff", font=_font(15, True))
        if 0 <= signal_idx < len(candles):
            xx, yy = x(signal_idx), y(candles[signal_idx]["high"])
            draw.line((xx - 48, yy - 36, xx, yy - 3), fill=_WHITE, width=2)
            draw.text((xx - 120, yy - 60), "ROMPIMENTO", fill=_WHITE, font=_font(13, True))

    if strategy_key == "DVP":
        p1 = _num(evidence.get("pivot_1_price"))
        p2 = _num(evidence.get("pivot_2_price"))
        p1_idx = _nearest_index(candles, evidence.get("pivot_1_time"))
        p2_idx = _nearest_index(candles, evidence.get("pivot_2_time"))
        if p1 and p2 and p1_idx >= 0 and p2_idx >= 0:
            draw.line((x(p1_idx), y(p1), x(p2_idx), y(p2)), fill=_BLUE, width=3)
            draw.text(((x(p1_idx)+x(p2_idx))/2 - 65, min(y(p1), y(p2)) + 18), "DIVERGÊNCIA DVP", fill=_BLUE, font=_font(13, True))
        if 0 <= event_idx < len(candles):
            xx, yy = x(event_idx), y(candles[event_idx]["high"])
            draw.line((xx - 48, yy - 34, xx, yy - 2), fill=_WHITE, width=2)
            draw.text((xx - 150, yy - 58), "CANDLE GATILHO", fill=_WHITE, font=_font(13, True))
    for label, value, color in levels:
        yy = y(value)
        left = x(max(0, event_idx - 4))
        draw.line((left, yy, chart_right, yy), fill=color, width=2)
        text = f"{label}  {_price(value)}"
        bbox = draw.textbbox((0, 0), text, font=_font(14, True))
        tw = bbox[2] - bbox[0]
        draw.rectangle((chart_right - tw - 20, yy - 22, chart_right - 4, yy + 2), fill="#08131b")
        draw.text((chart_right - tw - 12, yy - 20), text, fill=color, font=_font(14, True))

    draw.text((chart_left + 12, chart_top + 10), f"{symbol} · {timeframe}", fill=_TEXT, font=_font(17, True))
    draw.text((chart_left + 12, chart_top + 36), "HAGMARTK · EVIDÊNCIA PROSPECTIVA", fill=_MUTED, font=_font(12))
    draw.text((chart_left, 676), "Shadow / Simulação · Nenhuma ordem real foi enviada", fill=_MUTED, font=_font(14))
    draw.text((910, 676), "HAGMARTK · DISCIPLINA GERA EVIDÊNCIAS", fill=_GOLD, font=_font(13, True))

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
