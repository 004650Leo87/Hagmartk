const API_URL = 'http://127.0.0.1:8000';

async function apiRequest(endpoint, options = {}) {
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      Accept: 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Erro HTTP ${response.status}`;

    try {
      const errorData = await response.json();

      message =
        errorData?.detail ??
        errorData?.message ??
        message;
    } catch {
      // Mantém a mensagem padrão quando a resposta não é JSON.
    }

    throw new Error(message);
  }

  return response.json();
}

/* =====================================================
   MERCADO
===================================================== */

export async function getSymbols() {
  return apiRequest('/market/symbols');
}

export async function getQuote(symbol) {
  if (!symbol) {
    throw new Error('O ativo não foi informado.');
  }

  return apiRequest(
    `/market/quote/${encodeURIComponent(symbol)}`,
  );
}

export async function getQuotes() {
  return apiRequest('/market/quotes');
}

export async function getTimeframes() {
  return apiRequest('/market/timeframes');
}

export async function getSystemHealth() {
  return apiRequest('/system/health');
}

export async function getCandles(
  symbol,
  timeframe,
  bars = 300,
  offset = 0,
) {
  if (!symbol) {
    throw new Error('O ativo não foi informado.');
  }

  const parameters = new URLSearchParams();

  if (timeframe !== undefined && timeframe !== null) {
    parameters.set('timeframe', String(timeframe));
  }

  parameters.set('bars', String(bars));
  parameters.set('offset', String(offset));

  return apiRequest(
    `/market/candles/${encodeURIComponent(
      symbol,
    )}?${parameters.toString()}`,
  );
}

export async function getIndicators(
  symbol,
  timeframe,
  bars = 500,
  offset = 0,
  rsi = '14',
  ema = '50,200',
  sma = null,
) {
  if (!symbol) {
    throw new Error('O ativo não foi informado.');
  }

  const parameters = new URLSearchParams();

  if (timeframe !== undefined && timeframe !== null) {
    parameters.set('timeframe', String(timeframe));
  }

  parameters.set('bars', String(bars));
  parameters.set('offset', String(offset));

  if (rsi) parameters.set('rsi', String(rsi));
  if (ema) parameters.set('ema', String(ema));
  if (sma) parameters.set('sma', String(sma));

  return apiRequest(
    `/market/indicators/${encodeURIComponent(
      symbol,
    )}?${parameters.toString()}`,
  );
}

export async function getDivergences(
  symbol,
  timeframe = 'M15',
  bars = 500,
  offset = 0,
) {
  if (!symbol) {
    throw new Error('O ativo não foi informado.');
  }

  const parameters = new URLSearchParams();
  parameters.set('timeframe', String(timeframe));
  parameters.set('bars', String(bars));
  parameters.set('offset', String(offset));

  return apiRequest(
    `/strategy-lab/divergences/${encodeURIComponent(
      symbol,
    )}?${parameters.toString()}`,
  );
}

/* =====================================================
   CONTA
===================================================== */

export async function getAccount() {
  return apiRequest('/account');
}

export async function getAccountSummary() {
  return apiRequest('/account/summary');
}

export async function getAccountPositions() {
  return apiRequest('/account/positions');
}

export async function getTodayHistory() {
  return apiRequest('/account/history/today');
}