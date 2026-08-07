import { useEffect, useRef, useState } from 'react';
import { LineSeries } from 'lightweight-charts';
import { getCandles, getDivergences, getIndicators } from '../services/api';

import {
    createPriceScaleWheelHandler,
} from '../chart/chartPriceScale';

import {
    addChartEvents,
    removeChartEvents,
} from '../chart/chartEvents';

import {
    createVerticalNavigation,
} from '../chart/chartNavigation';

import {
    fetchChartCandles,
} from '../chart/chartLoader';

import {
    restoreChartViewport,
    saveChartViewport,
} from '../chart/chartViewport';

import {
    createMarketChart,
} from '../chart/chartFactory';


const HISTORY_PAGE_SIZE = 500;

function MarketChart({
    symbol = 'XAUUSD',
    timeframe = 'M5',
    refreshInterval = 2000,
    showRSI = false,
    showEMA50 = false,
    showEMA200 = false,
    showDivergences = false,
}) {
    const containerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const ema50SeriesRef = useRef(null);
    const ema200SeriesRef = useRef(null);
    const rsiSeriesRef = useRef(null);
    const divergenceSeriesRef = useRef([]);

    const [divergenceEvents, setDivergenceEvents] = useState([]);
    const [selectedDivergence, setSelectedDivergence] = useState(null);

    /*
     * Guarda qual ativo e timeframe pertencem atualmente
     * ao gráfico, sem depender dos valores antigos capturados
     * pelo primeiro useEffect.
     */
    const activeViewRef = useRef({
        symbol,
        timeframe,
    });

    /*
     * Guarda a função responsável pelo salvamento atual.
     */
    const saveCurrentViewRef = useRef(null);

    /*
     * Impede que eventos disparados durante a restauração
     * sobrescrevam a visualização que está sendo restaurada.
     */
    const restoringViewportRef = useRef(false);

    /*
     * Controla a primeira restauração após mudar
     * de ativo ou timeframe.
     */
    const viewportRestoredRef = useRef(false);

    const candlesRef = useRef([]);
    const nextOffsetRef = useRef(0);
    const loadingOlderRef = useRef(false);
    const hasMoreHistoryRef = useRef(true);

    /*
     * Mantém sempre a versão mais recente de loadOlderCandles
     * acessível ao handler registrado no useEffect do chart.
     */
    const loadOlderCandlesRef = useRef(null);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');


    /*
     * Criação única do gráfico.
     *
     * Este efeito não depende de symbol ou timeframe.
     * O gráfico permanece vivo enquanto o componente existir.
     */
    useEffect(() => {
        const container = containerRef.current;

        if (!container) {
            return undefined;
        }

        const {
            chart,
            series,
            ema50Series,
            ema200Series,
            rsiSeries,
        } = createMarketChart(container);

        chartRef.current = chart;
        seriesRef.current = series;
        ema50SeriesRef.current = ema50Series;
        ema200SeriesRef.current = ema200Series;
        rsiSeriesRef.current = rsiSeries;

        const priceScale = series.priceScale();

        /*
         * Esta função consulta activeViewRef no momento
         * em que for executada.
         *
         * Assim, ela nunca fica presa ao symbol/timeframe
         * existente na primeira renderização.
         */
        const saveCurrentView = () => {
            if (restoringViewportRef.current) {
                return;
            }

            const currentView = activeViewRef.current;

            if (
                !currentView?.symbol ||
                !currentView?.timeframe
            ) {
                return;
            }

            saveChartViewport({
                chart,
                series,
                symbol: currentView.symbol,
                timeframe: currentView.timeframe,
            });
        };

        saveCurrentViewRef.current = saveCurrentView;

                const {
            handlePointerDown: navigationPointerDown,
            handlePointerMove: navigationPointerMove,
            finishVerticalDrag: navigationFinishVerticalDrag,
        } = createVerticalNavigation({
            container,
            priceScale,
            series,
            saveCurrentView,
        });

        const handlePriceScaleWheel =
            createPriceScaleWheelHandler({
                container,
                priceScale,
                saveCurrentView,
            });

        const chartEvents = [
            {
                event: 'pointerdown',
                handler: navigationPointerDown,
                options: true,
            },
            {
                event: 'pointermove',
                handler: navigationPointerMove,
                options: true,
            },
            {
                event: 'pointerup',
                handler: navigationFinishVerticalDrag,
                options: true,
            },
            {
                event: 'pointercancel',
                handler: navigationFinishVerticalDrag,
                options: true,
            },
            {
                event: 'wheel',
                handler: handlePriceScaleWheel,
                options: {
                    capture: true,
                    passive: false,
                },
            },
        ];

        addChartEvents(container, chartEvents);

        const resizeChart = () => {
            chart.resize(
                Math.max(container.clientWidth, 1),
                Math.max(container.clientHeight, 1),
            );
        };

        resizeChart();

        const resizeObserver =
            new ResizeObserver(resizeChart);

        resizeObserver.observe(container);

        /*
         * Dispara loadOlderCandles quando o usuário navega
         * para perto do início esquerdo do histórico.
         *
         * Usa loadOlderCandlesRef para chamar sempre a versão
         * mais atual da função, mesmo que o closure do efeito
         * seja antigo.
         */
        const handleRangeChange = (range) => {
            if (
                range != null &&
                range.from != null &&
                range.from <= 5 &&
                !loadingOlderRef.current &&
                hasMoreHistoryRef.current
            ) {
                loadOlderCandlesRef.current?.();
            }
        };

        chart
            .timeScale()
            .subscribeVisibleLogicalRangeChange(
                handleRangeChange,
            );

        return () => {
            /*
             * Salva a visualização antes de destruir o gráfico.
             */
            saveCurrentView();

            removeChartEvents(
                container,
                chartEvents,
            );

                        resizeObserver.disconnect();

            chart
                .timeScale()
                .unsubscribeVisibleLogicalRangeChange(
                    handleRangeChange,
                );

            chart.remove();

            chartRef.current = null;
            seriesRef.current = null;
            ema50SeriesRef.current = null;
            ema200SeriesRef.current = null;
            rsiSeriesRef.current = null;
            saveCurrentViewRef.current = null;
        };
    }, []);

    useEffect(() => {
        const chart = chartRef.current;
        if (!chart) return;

        if (showRSI) {
            chart.priceScale('rsi_scale').applyOptions({
                visible: true,
                scaleMargins: { top: 0.75, bottom: 0.03 },
            });
            chart.priceScale('right').applyOptions({
                scaleMargins: { top: 0.05, bottom: 0.30 },
            });
        } else {
            chart.priceScale('rsi_scale').applyOptions({
                visible: false,
            });
            chart.priceScale('right').applyOptions({
                scaleMargins: { top: 0.08, bottom: 0.08 },
            });
            rsiSeriesRef.current?.setData([]);
        }

        if (!showEMA50) {
            ema50SeriesRef.current?.setData([]);
        }

        if (!showEMA200) {
            ema200SeriesRef.current?.setData([]);
        }
    }, [showRSI, showEMA50, showEMA200]);

    useEffect(() => {
        let active = true;

        const clearDivergences = () => {
            const chart = chartRef.current;
            if (chart && divergenceSeriesRef.current.length > 0) {
                divergenceSeriesRef.current.forEach((s) => {
                    try {
                        chart.removeSeries(s);
                    } catch {
                        // ignore
                    }
                });
                divergenceSeriesRef.current = [];
            }
        };

        if (!showDivergences) {
            clearDivergences();
            setDivergenceEvents([]);
            setSelectedDivergence(null);
            return undefined;
        }

        async function fetchAndRenderDivergences() {
            try {
                const data = await getDivergences(symbol, timeframe, HISTORY_PAGE_SIZE, 0);
                if (!active) return;
                const events = data?.events || [];
                setDivergenceEvents(events);

                clearDivergences();
                const chart = chartRef.current;
                if (!chart || events.length === 0) return;

                const parseTs = (tStr) => {
                    if (!tStr) return 0;
                    const d = new Date(tStr);
                    return Math.floor(d.getTime() / 1000);
                };

                const newSeriesList = [];

                events.forEach((evt) => {
                    const meta = evt.metadata;
                    if (!meta) return;

                    const isBear = evt.direction === 'BEARISH';
                    const color = isBear ? '#ff5f72' : '#21d68d';

                    const t1 = parseTs(meta.pivot_1_time);
                    const t2 = parseTs(meta.pivot_2_time);

                    if (t1 > 0 && t2 > 0) {
                        // Linha no gráfico principal (Preço)
                        const pLine = chart.addSeries(LineSeries, {
                            color,
                            lineWidth: 2,
                            priceLineVisible: false,
                            lastValueVisible: false,
                        });
                        pLine.setData([
                            { time: t1, value: meta.pivot_1_price },
                            { time: t2, value: meta.pivot_2_price },
                        ]);
                        newSeriesList.push(pLine);

                        // Linha no sub-painel RSI (se o RSI estiver visível)
                        if (showRSI) {
                            const rLine = chart.addSeries(LineSeries, {
                                color,
                                lineWidth: 2,
                                priceScaleId: 'rsi_scale',
                                priceLineVisible: false,
                                lastValueVisible: false,
                            });
                            rLine.setData([
                                { time: t1, value: meta.pivot_1_rsi },
                                { time: t2, value: meta.pivot_2_rsi },
                            ]);
                            newSeriesList.push(rLine);
                        }
                    }
                });

                divergenceSeriesRef.current = newSeriesList;
            } catch (err) {
                console.error('Erro ao carregar evidências de divergência:', err);
            }
        }

        fetchAndRenderDivergences();

        return () => {
            active = false;
            clearDivergences();
        };
    }, [showDivergences, showRSI, symbol, timeframe]);


    /*
     * Carregamento dos candles e troca de ativo/timeframe.
     */
    useEffect(() => {
        let active = true;
        let intervalId;

        /*
         * Neste momento activeViewRef ainda representa
         * a tela anterior.
         *
         * Portanto, primeiro salvamos a tela anterior.
         */
        saveCurrentViewRef.current?.();

        /*
         * Depois informamos que o gráfico agora pertence
         * ao novo ativo e ao novo timeframe.
         */
        activeViewRef.current = {
            symbol,
            timeframe,
        };

        candlesRef.current = [];
        nextOffsetRef.current = 0;
        loadingOlderRef.current = false;
        hasMoreHistoryRef.current = true;
        viewportRestoredRef.current = false;

        seriesRef.current?.setData([]);

        async function loadCandles() {
            try {
                setError('');

                const {
                    candles: recentCandles,
                } = await fetchChartCandles({
                    getCandles,
                    symbol,
                    timeframe,
                    limit: HISTORY_PAGE_SIZE,
                    offset: 0,
                });

                if (!active) {
                    return;
                }

                const chart = chartRef.current;
                const series = seriesRef.current;

                if (!chart || !series) {
                    return;
                }

                if (recentCandles.length === 0) {
                    setError(
                        `Nenhum candle válido foi recebido para ${symbol} ${timeframe}.`,
                    );

                    return;
                }

                const isInitialLoad =
                    candlesRef.current.length === 0;

                if (isInitialLoad) {
                    /*
                     * CARGA INICIAL: comportamento original
                     * preservado integralmente.
                     */
                    series.setData(recentCandles);

                    candlesRef.current = recentCandles;
                    nextOffsetRef.current = recentCandles.length;
                    hasMoreHistoryRef.current =
                        recentCandles.length === HISTORY_PAGE_SIZE;

                    /*
                     * Restaura apenas uma vez após mudar
                     * ativo ou timeframe.
                     */
                    if (!viewportRestoredRef.current) {
                        restoringViewportRef.current = true;

                        restoreChartViewport({
                            chart,
                            series,
                            symbol,
                            timeframe,
                            onRestored: () => {
                                /*
                                 * Confirma que essa restauração
                                 * ainda pertence à tela atual.
                                 */
                                const currentView =
                                    activeViewRef.current;

                                if (
                                    currentView.symbol === symbol &&
                                    currentView.timeframe === timeframe
                                ) {
                                    viewportRestoredRef.current = true;
                                }

                                restoringViewportRef.current = false;
                            },
                        });
                    }
                } else {
                    /*
                     * REFRESH RECENTE: merge incremental.
                     *
                     * Se loadOlderCandles estiver em andamento,
                     * pula esta rodada para evitar concorrência.
                     * O próximo ciclo do setInterval atualizará.
                     */
                    if (loadingOlderRef.current) {
                        return;
                    }

                    /*
                     * Constrói mapa a partir do histórico acumulado.
                     * Os candles recentes têm prioridade: sobrescrevem
                     * o candle existente quando o timestamp já existe
                     * (necessário para o candle atual em formação).
                     */
                    const byTime = new Map(
                        candlesRef.current.map((c) => [c.time, c]),
                    );

                    for (const c of recentCandles) {
                        byTime.set(c.time, c);
                    }

                    const merged = Array.from(
                        byTime.values(),
                    ).sort((a, b) => a.time - b.time);

                    candlesRef.current = merged;

                    series.setData(merged);
                }

                // Atualização dos indicadores ativos
                if (showRSI || showEMA50 || showEMA200) {
                    try {
                        const rsiParam = showRSI ? '14' : null;
                        const emaParam = [showEMA50 ? '50' : null, showEMA200 ? '200' : null]
                            .filter(Boolean)
                            .join(',') || null;

                        const indData = await getIndicators(
                            symbol,
                            timeframe,
                            candlesRef.current.length || HISTORY_PAGE_SIZE,
                            0,
                            rsiParam,
                            emaParam,
                        );

                        if (active && indData?.indicators) {
                            if (showRSI && indData.indicators.rsi_14) {
                                const rsiData = indData.indicators.rsi_14
                                    .filter((item) => item.value !== null)
                                    .map((item) => ({ time: item.time, value: item.value }));
                                rsiSeriesRef.current?.setData(rsiData);
                            }
                            if (showEMA50 && indData.indicators.ema_50) {
                                const ema50Data = indData.indicators.ema_50
                                    .filter((item) => item.value !== null)
                                    .map((item) => ({ time: item.time, value: item.value }));
                                ema50SeriesRef.current?.setData(ema50Data);
                            }
                            if (showEMA200 && indData.indicators.ema_200) {
                                const ema200Data = indData.indicators.ema_200
                                    .filter((item) => item.value !== null)
                                    .map((item) => ({ time: item.time, value: item.value }));
                                ema200SeriesRef.current?.setData(ema200Data);
                            }
                        }
                    } catch (indErr) {
                        console.error('Erro ao atualizar indicadores:', indErr);
                    }
                }
            } catch (requestError) {
                console.error(
                    'Erro ao carregar candles:',
                    requestError,
                );

                if (active) {
                    setError(
                        requestError?.message ||
                        'Não foi possível carregar os candles.',
                    );
                }
            } finally {
                if (active) {
                    setLoading(false);
                }
            }
        }

        setLoading(true);

        loadCandles();

        intervalId = window.setInterval(
            loadCandles,
            Math.max(refreshInterval, 1000),
        );

        return () => {
            active = false;

            window.clearInterval(intervalId);
        };
    }, [
        symbol,
        timeframe,
        refreshInterval,
        showRSI,
        showEMA50,
        showEMA200,
    ]);


    /*
     * Busca o próximo lote histórico e acumula sobre os
     * candles já carregados em candlesRef.
     *
     * Não conectado ao scroll ainda — chamada manual apenas.
     */
    async function loadOlderCandles() {
        if (
            loadingOlderRef.current ||
            !hasMoreHistoryRef.current
        ) {
            return;
        }

        loadingOlderRef.current = true;

        try {
            const { candles: olderCandles } =
                await fetchChartCandles({
                    getCandles,
                    symbol: activeViewRef.current.symbol,
                    timeframe: activeViewRef.current.timeframe,
                    limit: HISTORY_PAGE_SIZE,
                    offset: nextOffsetRef.current,
                });

            /*
             * Lote vazio ou menor que HISTORY_PAGE_SIZE
             * indica que não há mais histórico disponível.
             */
            if (olderCandles.length === 0) {
                hasMoreHistoryRef.current = false;
                return;
            }

            if (olderCandles.length < HISTORY_PAGE_SIZE) {
                hasMoreHistoryRef.current = false;
            }

            /*
             * Mescla com os candles existentes, usando
             * candle.time como chave única para eliminar
             * duplicatas e garantir ordem cronológica.
             */
            const existingByTime = new Map(
                candlesRef.current.map((c) => [c.time, c]),
            );

            const sizeBefore = existingByTime.size;

            for (const c of olderCandles) {
                if (!existingByTime.has(c.time)) {
                    existingByTime.set(c.time, c);
                }
            }

            const uniqueInsertedCount =
                existingByTime.size - sizeBefore;

            /*
             * Nenhum timestamp realmente novo → histórico
             * esgotado mesmo que o lote não estivesse vazio.
             */
            if (uniqueInsertedCount === 0) {
                hasMoreHistoryRef.current = false;
                return;
            }

            /*
             * Ordena o mapa em ordem cronológica crescente
             * e reconstrói o array acumulado.
             */
            const merged = Array.from(
                existingByTime.values(),
            ).sort((a, b) => a.time - b.time);

            /*
             * Captura a viewport atual ANTES do setData para
             * poder restaurá-la após o prepend sem causar salto.
             */
            const visibleRange =
                chartRef.current
                    ?.timeScale()
                    .getVisibleLogicalRange();

            candlesRef.current = merged;

            const series = seriesRef.current;

            if (series) {
                series.setData(merged);
            }

            /*
             * Desloca a viewport pelo número exato de
             * timestamps novos inseridos, mantendo o ponto
             * visual onde o usuário estava.
             */
            if (
                visibleRange != null &&
                visibleRange.from != null &&
                visibleRange.to != null &&
                uniqueInsertedCount > 0
            ) {
                chartRef.current
                    .timeScale()
                    .setVisibleLogicalRange({
                        from:
                            visibleRange.from +
                            uniqueInsertedCount,
                        to:
                            visibleRange.to +
                            uniqueInsertedCount,
                    });
            }

            /*
             * Avança o offset pelo tamanho do lote recebido
             * (não pelo número de timestamps novos) para que
             * a próxima requisição continue de onde parou.
             */
            nextOffsetRef.current += olderCandles.length;
        } catch (olderError) {
            console.error(
                'Erro ao carregar candles históricos:',
                olderError,
            );
        } finally {
            loadingOlderRef.current = false;
        }
    }

    /*
     * Mantém a ref sincronizada a cada render para que
     * handleRangeChange sempre invoque a versão atual.
     */
    loadOlderCandlesRef.current = loadOlderCandles;

    return (
        <div className="market-chart-shell">
            <div
                ref={containerRef}
                className="market-chart-canvas"
            />

            <div className="market-chart-watermark">
                <strong>{symbol}</strong>
                <span>{timeframe}</span>
            </div>

            {loading && (
                <div className="market-chart-state">
                    <strong>
                        Carregando candles reais...
                    </strong>
                </div>
            )}

            {!loading && error && (
                <div className="market-chart-state error">
                    <strong>
                        Não foi possível exibir o gráfico
                    </strong>

                    <span>{error}</span>
                </div>
            )}

            {showDivergences && divergenceEvents.length > 0 && (
                <div className="divergence-overlay-badge-list">
                    <span className="divergence-badge-title">Evidências HDM ({divergenceEvents.length}):</span>
                    {divergenceEvents.map((evt, idx) => {
                        const isBear = evt.direction === 'BEARISH';
                        return (
                            <button
                                key={idx}
                                type="button"
                                className={`divergence-badge ${isBear ? 'bearish' : 'bullish'} ${selectedDivergence === evt ? 'active' : ''}`}
                                onClick={() => setSelectedDivergence(evt)}
                            >
                                {isBear ? '🔻 Baixista' : '🔺 Altista'} #{idx + 1}
                            </button>
                        );
                    })}
                </div>
            )}

            {selectedDivergence && (
                <div className="divergence-card-overlay">
                    <div className="divergence-card-header">
                        <strong>HDM — Divergência ({selectedDivergence.direction === 'BEARISH' ? 'Baixista' : 'Altista'})</strong>
                        <button type="button" className="close-btn" onClick={() => setSelectedDivergence(null)}>✕</button>
                    </div>
                    <div className="divergence-card-body">
                        <div className="card-row">
                            <span>Ativo / Timeframe:</span>
                            <strong>{selectedDivergence.symbol} ({selectedDivergence.timeframe})</strong>
                        </div>
                        <div className="card-row">
                            <span>Pivô 1 (Preço | RSI):</span>
                            <strong>{selectedDivergence.metadata?.pivot_1_price} | RSI {selectedDivergence.metadata?.pivot_1_rsi}</strong>
                        </div>
                        <div className="card-row">
                            <span>Pivô 2 (Preço | RSI):</span>
                            <strong>{selectedDivergence.metadata?.pivot_2_price} | RSI {selectedDivergence.metadata?.pivot_2_rsi}</strong>
                        </div>
                        <div className="card-row">
                            <span>P1 Timestamp:</span>
                            <small>{selectedDivergence.metadata?.pivot_1_time}</small>
                        </div>
                        <div className="card-row">
                            <span>P2 Timestamp:</span>
                            <small>{selectedDivergence.metadata?.pivot_2_time}</small>
                        </div>
                        <div className="card-row">
                            <span>Confirmado em:</span>
                            <small>{selectedDivergence.metadata?.confirmed_at}</small>
                        </div>
                        <div className="card-row note">
                            <em>{selectedDivergence.reasons?.[0]}</em>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default MarketChart;