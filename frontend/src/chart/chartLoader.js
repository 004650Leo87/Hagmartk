import { prepareCandles } from './chartData';
import { timeframeCodes } from './chartConstants';

export async function fetchChartCandles({
    getCandles,
    symbol,
    timeframe,
    limit = 500,
}) {
    const timeframeCode =
        timeframeCodes[timeframe] ?? timeframeCodes.M5;

    const response = await getCandles(
        symbol,
        timeframeCode,
        limit,
    );

    const candles = prepareCandles(response);

    return {
        candles,
        timeframeCode,
    };
}