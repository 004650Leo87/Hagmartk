/**
 * Módulo de Cálculos de Indicadores no Frontend.
 *
 * Implementações puras e determinísticas em JavaScript de:
 * - EMA (Média Móvel Exponencial)
 * - RSI Wilder (Índice de Força Relativa de Wilder 14/N)
 * - RSI Divergence Engine (Port do Pine Script v6)
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

/**
 * Motor Visual de Detecção de Divergências Regulares no RSI (Port determinístico do Pine Script v6).
 *
 * Parâmetros padrão alinhados ao Pine Script enviado:
 * - lbL (lookbackLeft) = 5
 * - lbR (lookbackRight) = 5
 * - rangeLower = 5 (mínimo de barras entre pivôs)
 * - rangeUpper = 60 (máximo de barras entre pivôs)
 *
 * REGULAR BULLISH:
 * RSI faz Higher Low (rsi[P2] > rsi[P1]) enquanto Preço faz Lower Low (price[P2] < price[P1]).
 *
 * REGULAR BEARISH:
 * RSI faz Lower High (rsi[P2] < rsi[P1]) enquanto Preço faz Higher High (price[P2] > price[P1]).
 */
export function detectRegularRsiDivergences(
  candles = [],
  rsiData = [],
  options = {}
) {
  const lbL = options.lbL ?? 5;
  const lbR = options.lbR ?? 5;
  const rangeLower = options.rangeLower ?? 5;
  const rangeUpper = options.rangeUpper ?? 60;

  if (!candles || candles.length === 0 || !rsiData || rsiData.length === 0) {
    return [];
  }

  // Mapear rsiData em um mapa por tempo sincronizado com os candles
  const rsiMap = new Map();
  rsiData.forEach((item) => {
    if (item.time !== undefined && item.value !== null && item.value !== undefined) {
      rsiMap.set(item.time, item.value);
    }
  });

  // Construir dados pareados: { index, time, close, low, high, rsi }
  const points = [];
  candles.forEach((c, idx) => {
    if (rsiMap.has(c.time)) {
      points.push({
        index: idx,
        time: c.time,
        close: c.close ?? c.c ?? 0,
        low: c.low ?? c.l ?? (c.close ?? 0),
        high: c.high ?? c.h ?? (c.close ?? 0),
        rsi: rsiMap.get(c.time),
      });
    }
  });

  if (points.length < lbL + lbR + 1) return [];

  // 1. Identificar Pivôs de Fundo (Pivot Lows) e Pivôs de Topo (Pivot Highs) no RSI
  const pivotLows = [];
  const pivotHighs = [];

  for (let i = lbL; i < points.length - lbR; i++) {
    const currentRsi = points[i].rsi;

    // Checar Pivot Low no RSI: rsi[i] menor que vizinhos da esquerda e menor ou igual aos da direita
    let isPivotLow = true;
    for (let k = 1; k <= lbL; k++) {
      if (points[i - k].rsi <= currentRsi) {
        isPivotLow = false;
        break;
      }
    }
    if (isPivotLow) {
      for (let k = 1; k <= lbR; k++) {
        if (points[i + k].rsi < currentRsi) {
          isPivotLow = false;
          break;
        }
      }
    }
    if (isPivotLow) {
      pivotLows.push(points[i]);
    }

    // Checar Pivot High no RSI: rsi[i] maior que vizinhos da esquerda e maior ou igual aos da direita
    let isPivotHigh = true;
    for (let k = 1; k <= lbL; k++) {
      if (points[i - k].rsi >= currentRsi) {
        isPivotHigh = false;
        break;
      }
    }
    if (isPivotHigh) {
      for (let k = 1; k <= lbR; k++) {
        if (points[i + k].rsi > currentRsi) {
          isPivotHigh = false;
          break;
        }
      }
    }
    if (isPivotHigh) {
      pivotHighs.push(points[i]);
    }
  }

  const divergences = [];

  // 2. Detecção de Regular Bullish Divergence (Pivôs de Fundo)
  for (let i = 1; i < pivotLows.length; i++) {
    const p2 = pivotLows[i];
    for (let j = i - 1; j >= 0; j--) {
      const p1 = pivotLows[j];
      const barsBetween = p2.index - p1.index;

      if (barsBetween >= rangeLower && barsBetween <= rangeUpper) {
        // REGULAR BULLISH: RSI faz Higher Low (p2.rsi > p1.rsi) AND Preço faz Lower Low (p2.low < p1.low)
        if (p2.rsi > p1.rsi && p2.low < p1.low) {
          divergences.push({
            type: 'BULLISH',
            p1Time: p1.time,
            p1Rsi: p1.rsi,
            p1Price: p1.low,
            p2Time: p2.time,
            p2Rsi: p2.rsi,
            p2Price: p2.low,
            barsBetween,
          });
          break;
        }
      } else if (barsBetween > rangeUpper) {
        break;
      }
    }
  }

  // 3. Detecção de Regular Bearish Divergence (Pivôs de Topo)
  for (let i = 1; i < pivotHighs.length; i++) {
    const p2 = pivotHighs[i];
    for (let j = i - 1; j >= 0; j--) {
      const p1 = pivotHighs[j];
      const barsBetween = p2.index - p1.index;

      if (barsBetween >= rangeLower && barsBetween <= rangeUpper) {
        // REGULAR BEARISH: RSI faz Lower High (p2.rsi < p1.rsi) AND Preço faz Higher High (p2.high > p1.high)
        if (p2.rsi < p1.rsi && p2.high > p1.high) {
          divergences.push({
            type: 'BEARISH',
            p1Time: p1.time,
            p1Rsi: p1.rsi,
            p1Price: p1.high,
            p2Time: p2.time,
            p2Rsi: p2.rsi,
            p2Price: p2.high,
            barsBetween,
          });
          break;
        }
      } else if (barsBetween > rangeUpper) {
        break;
      }
    }
  }

  return divergences;
}
