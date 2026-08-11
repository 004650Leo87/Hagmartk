export function normalizeCandle(candle) {
    if (!candle) {
        return null;
    }

    const open = Number(candle.open);
    const high = Number(candle.high);
    const low = Number(candle.low);
    const close = Number(candle.close);

    let timeVal = candle.time;
    let timestamp = 0;

    if (typeof timeVal === 'number') {
        timestamp = timeVal > 1e11 ? Math.floor(timeVal / 1000) : Math.floor(timeVal);
    } else if (typeof timeVal === 'string') {
        const isoStr = timeVal.includes(' ') ? timeVal.replace(' ', 'T') : timeVal;
        const parsed = new Date(isoStr).getTime();
        if (Number.isFinite(parsed)) {
            timestamp = Math.floor(parsed / 1000);
        } else {
            const num = Number(timeVal);
            if (Number.isFinite(num)) {
                timestamp = num > 1e11 ? Math.floor(num / 1000) : Math.floor(num);
            }
        }
    }

    if (
        !Number.isFinite(open) ||
        !Number.isFinite(high) ||
        !Number.isFinite(low) ||
        !Number.isFinite(close) ||
        !timestamp ||
        timestamp <= 0
    ) {
        return null;
    }

    return {
        time: timestamp,
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

export function mergeCandles(existingCandles = [], newCandles = []) {
    const map = new Map();

    for (const candle of existingCandles) {
        if (candle && typeof candle.time === 'number') {
            map.set(candle.time, candle);
        }
    }

    for (const candle of newCandles) {
        if (candle && typeof candle.time === 'number') {
            map.set(candle.time, candle);
        }
    }

    const merged = Array.from(map.values()).sort((a, b) => a.time - b.time);

    let addedBeforeCount = 0;
    if (existingCandles.length > 0) {
        const oldMinTime = existingCandles[0].time;
        addedBeforeCount = merged.filter((c) => c.time < oldMinTime).length;
    }

    return {
        merged,
        addedBeforeCount,
    };
}