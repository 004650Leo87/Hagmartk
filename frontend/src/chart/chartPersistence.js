const STORAGE_KEY = "hagmartk.chart.views";

function loadStorage() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveStorage(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function makeKey(symbol, timeframe) {
  return `${symbol}_${timeframe}`;
}

export function saveChartView(symbol, timeframe, view) {
  const storage = loadStorage();

  storage[makeKey(symbol, timeframe)] = {
    ...view,
    updatedAt: Date.now(),
  };

  saveStorage(storage);
}

export function loadChartView(symbol, timeframe) {
  const storage = loadStorage();

  return storage[makeKey(symbol, timeframe)] || null;
}

export function clearChartView(symbol, timeframe) {
  const storage = loadStorage();

  delete storage[makeKey(symbol, timeframe)];

  saveStorage(storage);
}

export function clearAllChartViews() {
  localStorage.removeItem(STORAGE_KEY);
}