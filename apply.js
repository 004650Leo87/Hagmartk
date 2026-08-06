const fs = require('fs');

let content = fs.readFileSync('frontend/src/components/MarketChart.jsx', 'utf8');

content = content.replace('function MarketChart({', 'const HISTORY_PAGE_SIZE = 500;\n\nfunction MarketChart({');

const historyRefStr = `
    const historyRef = useRef({
        symbol,
        timeframe,
        candles: [],
        nextOffset: 0,
        hasMoreHistory: true,
        loadingInitial: false,
        loadingOlder: false,
        loadingRecent: false,
        requestId: 0,
        active: true,
    });

    function mergeCandles(existing, update, preferUpdate = true) {
        const candleMap = new Map();
        for (const candle of existing) {
            candleMap.set(candle.time, candle);
        }
        for (const candle of update) {
            if (preferUpdate || !candleMap.has(candle.time)) {
                candleMap.set(candle.time, candle);
            }
        }
        return Array.from(candleMap.values()).sort((a, b) => a.time - b.time);
    }
`;

content = content.replace('const viewportRestoredRef = useRef(false);', 'const viewportRestoredRef = useRef(false);\n' + historyRefStr);


const secondUseEffectStr = `
    useEffect(() => {
        let intervalId;

        saveCurrentViewRef.current?.();
        activeViewRef.current = { symbol, timeframe };
        viewportRestoredRef.current = false;

        const currentRequestId = historyRef.current.requestId + 1;

        historyRef.current = {
            symbol,
            timeframe,
            candles: [],
            nextOffset: 0,
            hasMoreHistory: true,
            loadingInitial: false,
            loadingOlder: false,
            loadingRecent: false,
            requestId: currentRequestId,
            active: true,
        };

        const chart = chartRef.current;
        const series = seriesRef.current;

        async function fetchBatch(offset, prepend, isRecentUpdate) {
            const history = historyRef.current;
            if (history.requestId !== currentRequestId || !history.active) return;

            try {
                const { candles } = await fetchChartCandles({
                    getCandles,
                    symbol,
                    timeframe,
                    limit: HISTORY_PAGE_SIZE,
                    offset,
                });

                if (history.requestId !== currentRequestId || !history.active) return;
                if (!chart || !series) return;

                const previousCandles = history.candles;
                
                const nextCandles = prepend 
                    ? mergeCandles(candles, previousCandles, false) 
                    : isRecentUpdate
                    ? mergeCandles(previousCandles, candles, true)
                    : candles;

                const uniqueInsertedCount = prepend && previousCandles.length > 0 
                    ? nextCandles.length - previousCandles.length 
                    : candles.length;

                history.candles = nextCandles;
                setCandleCount(nextCandles.length);

                if (!isRecentUpdate) {
                    history.nextOffset = offset + candles.length;
                }

                if (prepend) {
                    history.hasMoreHistory = candles.length > 0 && uniqueInsertedCount > 0;
                } else if (!isRecentUpdate) {
                    history.hasMoreHistory = candles.length === HISTORY_PAGE_SIZE;
                }

                const visibleRange = chart.timeScale().getVisibleLogicalRange();
                series.setData(nextCandles);

                if (prepend && visibleRange?.from != null && visibleRange?.to != null) {
                    chart.timeScale().setVisibleLogicalRange({
                        from: visibleRange.from + uniqueInsertedCount,
                        to: visibleRange.to + uniqueInsertedCount,
                    });
                }

                if (!viewportRestoredRef.current && !prepend && !isRecentUpdate) {
                    restoringViewportRef.current = true;
                    restoreChartViewport({
                        chart,
                        series,
                        symbol,
                        timeframe,
                        onRestored: () => {
                            if (activeViewRef.current.symbol === symbol && activeViewRef.current.timeframe === timeframe) {
                                viewportRestoredRef.current = true;
                            }
                            restoringViewportRef.current = false;
                        },
                    });
                }

                return { success: true, count: nextCandles.length };
            } catch (err) {
                console.error('Erro ao carregar candles:', err);
                if (history.active && history.requestId === currentRequestId) {
                    setError(err?.message || 'Não foi possível carregar os candles.');
                }
                return { success: false, error: err };
            }
        }

        async function loadInitial() {
            const history = historyRef.current;
            if (history.loadingInitial) return;
            history.loadingInitial = true;
            setError('');
            
            await fetchBatch(0, false, false);
            
            if (history.active && history.requestId === currentRequestId) {
                history.loadingInitial = false;
                setLoading(false);
            }
        }

        async function loadRecentCandles() {
            const history = historyRef.current;
            if (history.loadingRecent || history.loadingInitial) return;
            history.loadingRecent = true;
            
            await fetchBatch(0, false, true);
            
            if (history.active && history.requestId === currentRequestId) {
                history.loadingRecent = false;
            }
        }

        async function loadOlderCandles() {
            const history = historyRef.current;
            if (history.loadingOlder || !history.hasMoreHistory || history.nextOffset === 0) return;
            
            history.loadingOlder = true;
            await fetchBatch(history.nextOffset, true, false);
            
            if (history.active && history.requestId === currentRequestId) {
                history.loadingOlder = false;
            }
        }

        function handleVisibleRangeChange() {
            saveCurrentViewRef.current?.();
            const history = historyRef.current;
            if (!chart || history.requestId !== currentRequestId || !history.active) return;
            
            const range = chart.timeScale().getVisibleLogicalRange();
            if (history.hasMoreHistory && !history.loadingOlder && range?.from != null && range.from <= 5) {
                loadOlderCandles();
            }
        }

        if (chart) {
            chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
        }

        setLoading(true);
        setCandleCount(0);
        
        loadInitial();

        intervalId = window.setInterval(loadRecentCandles, Math.max(refreshInterval, 1000));

        return () => {
            historyRef.current.active = false;
            window.clearInterval(intervalId);
            if (chart) {
                chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
            }
        };
    }, [symbol, timeframe, refreshInterval]);
`;

const match = content.match(/useEffect\(\(\) => \{[\s\S]*?setLoading\(true\);\s*setCandleCount\(0\);[\s\S]*?loadCandles\(\);[\s\S]*?intervalId = window\.setInterval\([\s\S]*?\);\s*return \(\) => \{[\s\S]*?\};\s*\}, \[[\s\S]*?\]\);/);

if (match) {
    content = content.replace(match[0], secondUseEffectStr);
    fs.writeFileSync('frontend/src/components/MarketChart.jsx', content);
    console.log('Successfully updated MarketChart.jsx');
} else {
    console.log('Could not find the second useEffect block to replace');
}
