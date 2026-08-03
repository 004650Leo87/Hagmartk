const API_URL = 'http://127.0.0.1:8000';

export async function getSymbols() {
  const response = await fetch(`${API_URL}/market/symbols`);

  if (!response.ok) {
    throw new Error('Não foi possível carregar os ativos.');
  }

  return response.json();
}

export async function getCandles() {
  const response = await fetch(`${API_URL}/market/candles`);

  if (!response.ok) {
    throw new Error('Não foi possível carregar os candles.');
  }

  return response.json();
}