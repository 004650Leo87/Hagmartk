const API_URL = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL : 'http://127.0.0.1:8000';

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

export async function getHDFEvidences(symbol, timeframe) {
  const queryParams = new URLSearchParams();
  if (timeframe) queryParams.append('timeframe', timeframe);
  const queryString = queryParams.toString() ? `?${queryParams.toString()}` : '';
  return apiRequest(`/api/shadow/evidence/by-symbol/${encodeURIComponent(symbol)}${queryString}`);
}

export async function getHDFFunnel(symbol, timeframe) {
  const queryParams = new URLSearchParams();
  if (symbol) queryParams.append('symbol', symbol);
  if (timeframe) queryParams.append('timeframe', timeframe);
  const queryString = queryParams.toString() ? `?${queryParams.toString()}` : '';
  return apiRequest(`/api/shadow/funnel${queryString}`);
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

/* =====================================================
   SHADOW MODE
===================================================== */

export async function getShadowStatus() {
  return apiRequest('/api/shadow/status');
}

export async function getShadowCandidates() {
  return apiRequest('/api/shadow/candidates');
}

export async function enableShadowCandidate(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/${encodeURIComponent(candidateId)}/enable`, {
    method: 'POST',
  });
}

export async function disableShadowCandidate(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/${encodeURIComponent(candidateId)}/disable`, {
    method: 'POST',
  });
}

export async function getShadowEvents() {
  return apiRequest('/api/shadow/events');
}

export async function getShadowEventDetail(eventId) {
  return apiRequest(`/api/shadow/events/${encodeURIComponent(eventId)}`);
}

export async function getActiveShadowAlerts() {
  return apiRequest('/api/shadow/active');
}

export async function getCompletedShadowHistory() {
  return apiRequest('/api/shadow/history');
}

export async function getShadowStatistics() {
  return apiRequest('/api/shadow/statistics');
}

export async function getShadowScanners() {
  return apiRequest('/api/shadow/scanners');
}

/* =====================================================
   WATCHLIST
===================================================== */

export async function getWatchlist() {
  return apiRequest('/market/watchlist');
}

export async function getWatchlistSymbols() {
  return apiRequest('/market/watchlist/symbols');
}

export async function addToWatchlist(symbol) {
  return apiRequest('/market/watchlist/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol }),
  });
}

export async function removeFromWatchlist(symbol) {
  return apiRequest(`/market/watchlist/${encodeURIComponent(symbol)}`, {
    method: 'DELETE',
  });
}

export async function getMarketCatalog() {
  return apiRequest('/market/catalog');
}

/* =====================================================
   SHADOW EVENTS EXTRAS
===================================================== */

export async function getShadowRecentEvents(n = 20) {
  return apiRequest(`/api/shadow/events/recent?n=${n}`);
}

export async function getHDFRecentEvidences(limit = 100) {
  return apiRequest(`/api/shadow/evidence/recent?limit=${limit}`);
}

export async function getShadowEventsPage(limit = 20, offset = 0) {
  return apiRequest(`/api/shadow/events?limit=${limit}&offset=${offset}`);
}

export async function getShadowNavigationPayload(eventId) {
  return apiRequest(`/api/shadow/navigation/${encodeURIComponent(eventId)}`);
}

export async function getShadowCatalog() {
  return apiRequest('/api/shadow/catalog');
}

export async function getShadowForwardValidation(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/forward-validation?candidate_id=${encodeURIComponent(candidateId)}`);
}

export async function getShadowStatisticalValidation(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/statistical-validation?candidate_id=${encodeURIComponent(candidateId)}`);
}

export async function getShadowTelemetry(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/telemetry?candidate_id=${encodeURIComponent(candidateId)}`);
}

export async function getShadowIntelligence(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/intelligence?candidate_id=${encodeURIComponent(candidateId)}`);
}

export async function getShadowEvidence(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/evidence?candidate_id=${encodeURIComponent(candidateId)}`);
}

export async function getShadowObservationHealth(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/observation/health?candidate_id=${encodeURIComponent(candidateId)}`);
}

export async function getShadowObservationProgress(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/observation/progress?candidate_id=${encodeURIComponent(candidateId)}`);
}

export async function getShadowObservationHistory(candidateId = 'hdf_dvp_exit_2r', symbol = null, timeframe = null) {
  let url = `/api/shadow/observation/history?candidate_id=${encodeURIComponent(candidateId)}`;
  if (symbol) url += `&symbol=${encodeURIComponent(symbol)}`;
  if (timeframe) url += `&timeframe=${encodeURIComponent(timeframe)}`;
  return apiRequest(url);
}

export async function getShadowObservationDrilldown(symbol, timeframe, candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/observation/${encodeURIComponent(symbol)}/${encodeURIComponent(timeframe)}?candidate_id=${encodeURIComponent(candidateId)}`);
}

export async function getShadowHeartbeat(candidateId = 'hdf_dvp_exit_2r') {
  return apiRequest(`/api/shadow/heartbeat?candidate_id=${encodeURIComponent(candidateId)}`);
}