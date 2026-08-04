export function normalizeCandle(candle) {
    if (!candle) {
        return null;
    }

    const open = Number(candle.open);
    const high = Number(candle.high);
    const low = Number(candle.low);
    const close = Number(candle.close);
    const timestamp = new Date(candle.time).getTime();

    if (
        !Number.isFinite(open) ||
        !Number.isFinite(high) ||
        !Number.isFinite(low) ||
        !Number.isFinite(close) ||
        !Number.isFinite(timestamp)
    ) {
        return null;
    }

    return {
        time: Math.floor(timestamp / 1000),
        open,
        high,
        low,
        close,
    };
}

export function prepareCandles(response) {
    const source = Array.isArray(response)
        ? response
        : Array.isArray(response?.data)
          ? response.data
          : Array.isArray(response?.candles)
            ? response.candles
            : [];

    return source
        .map(normalizeCandle)
        .filter(Boolean)
        .sort((a, b) => a.time - b.time);
}