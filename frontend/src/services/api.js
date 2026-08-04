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

export async function getCandles(
  symbol,
  timeframe,
  bars = 300,
) {
  if (!symbol) {
    throw new Error('O ativo não foi informado.');
  }

  const parameters = new URLSearchParams();

  if (timeframe !== undefined && timeframe !== null) {
    parameters.set('timeframe', String(timeframe));
  }

  parameters.set('bars', String(bars));

  return apiRequest(
    `/market/candles/${encodeURIComponent(
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