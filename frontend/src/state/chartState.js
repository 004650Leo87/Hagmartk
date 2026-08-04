const chartStates = {};

function getStateKey(symbol, timeframe) {
    return `${symbol}:${timeframe}`;
}

export function getChartState(symbol, timeframe) {
    const key = getStateKey(symbol, timeframe);
    return chartStates[key] || null;
}

export function saveChartState(symbol, timeframe, state) {
    const key = getStateKey(symbol, timeframe);

    chartStates[key] = {
        ...chartStates[key],
        ...state,
    };
}

export function clearChartState(symbol, timeframe) {
    const key = getStateKey(symbol, timeframe);
    delete chartStates[key];
}

export function clearAllChartStates() {
    Object.keys(chartStates).forEach((key) => {
        delete chartStates[key];
    });
}

export default chartStates;