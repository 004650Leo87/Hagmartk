from __future__ import annotations

from typing import Dict

# Tabela centralizada de timeframes suportados pelo MetaTrader 5
SUPPORTED_TIMEFRAMES: Dict[str, int] = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M6": 6,
    "M10": 10,
    "M12": 12,
    "M15": 15,
    "M20": 20,
    "M30": 30,
    "H1": 16385,
    "H2": 16386,
    "H3": 16387,
    "H4": 16388,
    "H6": 16390,
    "H8": 16392,
    "H12": 16396,
    "D1": 16408,
    "W1": 32769,
    "MN1": 49153,
}

TIMEFRAME_CODE_TO_NAME: Dict[int, str] = {
    code: name for name, code in SUPPORTED_TIMEFRAMES.items()
}

# Duracao nominal em minutos. Usada por scanners para fechamento de candle,
# telemetria e staleness. Mantida separada dos codigos MT5 (H1+ nao sao minutos).
TIMEFRAME_MINUTES: Dict[str, int] = {
    "M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5, "M6": 6,
    "M10": 10, "M12": 12, "M15": 15, "M20": 20, "M30": 30,
    "H1": 60, "H2": 120, "H3": 180, "H4": 240, "H6": 360,
    "H8": 480, "H12": 720, "D1": 1440, "W1": 10080, "MN1": 43200,
}


def categorize_symbol(path: str = "", name: str = "", description: str = "") -> str:
    """Classifica o símbolo em uma categoria padronizada.

    Categorias: FOREX, METALS, ENERGY, CRYPTO, INDICES, STOCKS, OTHER.
    Preserva o caminho original da corretora (broker_path) em campo separado.
    """
    combined = f"{path} {name} {description}".upper()

    if any(k in combined for k in ["METAL", "GOLD", "SILVER", "PLATINUM", "PALLADIUM", "XAU", "XAG"]):
        return "METALS"

    if any(k in combined for k in ["ENERGY", "OIL", "BRENT", "WTI", "GAS", "CRUDE"]):
        return "ENERGY"

    if any(k in combined for k in ["CRYPTO", "BITCOIN", "BTC", "ETH", "SOL", "XRP"]):
        return "CRYPTO"

    if any(k in combined for k in ["INDEX", "INDICES", "US30", "US500", "NAS100", "GER40", "UK100", "SPX"]):
        return "INDICES"

    if any(k in combined for k in ["STOCK", "SHARE", "EQUITY", "AAPL", "MSFT", "AMZN", "NVDA", "TSLA"]):
        return "STOCKS"

    if any(k in combined for k in ["FOREX", "FX", "CURRENCY"]) or (len(name) == 6 and name.isalpha() and not path):
        return "FOREX"

    # Default fallback quando o caminho/nome for genérico de pares FX
    if any(pair in name.upper() for pair in ["EUR", "USD", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]):
        return "FOREX"

    return "OTHER"
