import { prepareCandles } from './chartData';
import { timeframeCodes } from './chartConstants';

export async function fetchChartCandles({
    getCandles,
    symbol,
    timeframe,
    timeframeMap,
    limit = 500,
    offset = 0,
}) {
    const timeframeCode =
        typeof timeframe === 'number'
            ? timeframe
            : timeframeMap?.[timeframe] ??
              timeframeCodes[timeframe] ??
              timeframeCodes.M5;

    const response = await getCandles(
        symbol,
        timeframeCode,
        limit,
        offset,
    );

    const candles = prepareCandles(response);

    return {
        candles,
        timeframeCode,
    };
}