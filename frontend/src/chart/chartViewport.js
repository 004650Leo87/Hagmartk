import { loadChartView, saveChartView } from './chartPersistence';
export function restoreChartViewport({

    
    chart,
    series,
    symbol,
    timeframe,
    onRestored,
}) {
    if (!chart || !series) {
        return;
    }

    const savedView = loadChartView(symbol, timeframe);

    requestAnimationFrame(() => {
        const priceScale = series.priceScale();

        if (savedView?.logicalRange) {
            chart
                .timeScale()
                .setVisibleLogicalRange(savedView.logicalRange);
        } else {
            chart.timeScale().fitContent();
        }

        if (savedView?.priceRange) {
            priceScale.setAutoScale(false);
            priceScale.setVisibleRange(savedView.priceRange);
        } else {
            priceScale.setAutoScale(
                savedView?.autoScale ?? true,
            );
        }

        onRestored?.();
    });
}
export function saveChartViewport({
    chart,
    series,
    symbol,
    timeframe,
}) {
    const priceScale = series.priceScale();

    const logicalRange = chart.timeScale().getVisibleLogicalRange();
    const priceRange = priceScale.getVisibleRange();

    saveChartView(symbol, timeframe, {
        logicalRange: logicalRange
            ? {
                  from: logicalRange.from,
                  to: logicalRange.to,
              }
            : null,
        priceRange,
        autoScale: priceScale.options().autoScale,
    });

    return {
        logicalRange,
        priceRange,
    };
}