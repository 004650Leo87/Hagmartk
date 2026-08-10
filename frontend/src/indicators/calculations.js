/**
 * Módulo de Cálculos de Indicadores no Frontend.
 *
 * Implementações puras e determinísticas em JavaScript de:
 * - EMA (Média Móvel Exponencial)
 * - RSI Wilder (Índice de Força Relativa de Wilder 14/N)
 */

export function calculateEMA(candles = [], period = 20) {
  if (!candles || candles.length < period || period <= 0) return [];

  const results = [];
  const k = 2 / (period + 1);

  // Calcula SMA inicial como semente da EMA
  let sum = 0;
  for (let i = 0; i < period; i++) {
    const val = candles[i]?.close ?? candles[i]?.c ?? 0;
    sum += val;
  }
  let ema = sum / period;

  const t0 = candles[period - 1]?.time;
  if (t0 !== undefined) {
    results.push({ time: t0, value: ema });
  }

  for (let i = period; i < candles.length; i++) {
    const close = candles[i]?.close ?? candles[i]?.c ?? 0;
    const time = candles[i]?.time;
    ema = close * k + ema * (1 - k);
    if (time !== undefined) {
      results.push({ time, value: ema });
    }
  }

  return results;
}

export function calculateRSI(candles = [], period = 14) {
  if (!candles || candles.length <= period || period <= 0) return [];

  const results = [];
  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const prevClose = candles[i - 1]?.close ?? candles[i - 1]?.c ?? 0;
    const currClose = candles[i]?.close ?? candles[i]?.c ?? 0;
    const diff = currClose - prevClose;
    if (diff >= 0) {
      gains += diff;
    } else {
      losses += Math.abs(diff);
    }
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  let rsi = 100 - 100 / (1 + rs);

  const t0 = candles[period]?.time;
  if (t0 !== undefined) {
    results.push({ time: t0, value: rsi });
  }

  for (let i = period + 1; i < candles.length; i++) {
    const prevClose = candles[i - 1]?.close ?? candles[i - 1]?.c ?? 0;
    const currClose = candles[i]?.close ?? candles[i]?.c ?? 0;
    const diff = currClose - prevClose;

    const gain = diff >= 0 ? diff : 0;
    const loss = diff < 0 ? Math.abs(diff) : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi = 100 - 100 / (1 + rs);

    const time = candles[i]?.time;
    if (time !== undefined) {
      results.push({ time, value: rsi });
    }
  }

  return results;
}
