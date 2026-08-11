import { useEffect, useRef, useState } from 'react';
import { LineSeries } from 'lightweight-charts';
import { getCandles, getDivergences, getHDFEvidences, getIndicators } from '../services/api';
import { calculateEMA, calculateRSI, detectRegularRsiDivergences } from '../indicators/calculations';

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
    timeframe = 'H1',
    timeframeMap = {},
    refreshInterval = 2000,
    userIndicators = [],
    onToggleIndicatorVisibility = null,
    onRemoveIndicator = null,
    onOpenIndicatorSettings = null,
    showRSI = true,
    onToggleRSI = null,
    showEMA50 = false,
    showEMA200 = false,
    showDivergences = false,
    theme = 'black-piano',
    activeEvidenceEventId = null,
    activeEvidenceData = null,
    onClearEvidence = null,
}) {
    const containerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const ema50SeriesRef = useRef(null);
    const ema200SeriesRef = useRef(null);
    const rsiSeriesRef = useRef(null);
    const divergenceSeriesRef = useRef([]);
    const userIndicatorSeriesRef = useRef(new Map());

    const [divergenceEvents, setDivergenceEvents] = useState([]);
    const [selectedDivergence, setSelectedDivergence] = useState(null);
    const [legendCollapsedPrice, setLegendCollapsedPrice] = useState(false);
    const [legendCollapsedRSI, setLegendCollapsedRSI] = useState(false);
    const [showDivergencesToggle, setShowDivergencesToggle] = useState(true);

    const overlayIndicators = (userIndicators || []).filter((i) => i.type === 'ema');
    const oscillatorIndicators = (userIndicators || []).filter((i) => i.type === 'rsi');
    const hasVisibleRSI = (userIndicators || []).some((i) => i.type === 'rsi' && i.visible) || showRSI || !!activeEvidenceEventId;

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
        } = createMarketChart(container, theme);

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
            chart,
            saveCurrentView,
        });

        const handlePriceScaleWheel = createPriceScaleWheelHandler({
            container,
            chart,
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

/* Efeito para alternância dinâmica do tema no gráfico */
useEffect(() => {
    if (!chartRef.current) return;
    const isLight = theme === 'flight-deck-light' || theme === 'light';
    const bgColor = isLight ? '#f8fafc' : '#050a11';
    const textColor = isLight ? '#334155' : '#8194b2';
    const gridColor = isLight ? 'rgba(203, 213, 225, 0.45)' : 'rgba(116, 137, 168, 0.08)';
    const borderColor = isLight ? '#cbd5e1' : '#1d2a3c';
    const crosshairColor = isLight ? 'rgba(100, 116, 139, 0.4)' : 'rgba(116, 137, 168, 0.3)';

    try {
        chartRef.current.applyOptions({
            layout: {
                background: {
                    type: ColorType.Solid,
                    color: bgColor,
                },
                textColor: textColor,
            },
            grid: {
                vertLines: { color: gridColor },
                horzLines: { color: gridColor },
            },
            crosshair: {
                vertLine: { color: crosshairColor },
                horzLine: { color: crosshairColor },
            },
            rightPriceScale: {
                borderColor: borderColor,
            },
            timeScale: {
                borderColor: borderColor,
            },
        });

        try {
            chartRef.current.priceScale('right', 0)?.applyOptions({
                borderColor: borderColor,
                textColor: textColor,
            });
            chartRef.current.priceScale('right', 1)?.applyOptions({
                borderColor: borderColor,
                textColor: textColor,
            });
        } catch { }
    } catch (e) {
        console.error('[THEME UPDATE] Erro ao aplicar opções de tema no gráfico:', e);
    }
}, [theme]);



    useEffect(() => {
        let active = true;

        if (!showDivergences) {
            setDivergenceEvents([]);
            setSelectedDivergence(null);
            return undefined;
        }

        async function fetchAndRenderDivergences() {
            try {
                const data = await getDivergences(symbol, timeframe, HISTORY_PAGE_SIZE, 0);
                if (!active) return;
                const events = data?.events || [];
                // Alimenta o EvidenceDrawer para consulta histórica de pesquisa.
                // NÃO desenha automaticamente linhas brutas acumuladas sobre o gráfico operacional.
                setDivergenceEvents(events);
            } catch (err) {
                console.error('Erro ao carregar divergências históricas:', err);
            }
        }

        fetchAndRenderDivergences();

        return () => {
            active = false;
        };
    }, [showDivergences, symbol, timeframe]);

    // HDF-Governed RSI Divergence Visual Engine (Fase 5C.13):
    // A linha visual de divergência no RSI SOMENTE pode existir quando houver um EVENTO HDF VÁLIDO.
    // Sem evento HDF ativo/selecionado -> ZERO LINHAS (RSI permanece 100% limpo).
    useEffect(() => {
        let isMounted = true;
        const chart = chartRef.current;
        const mainSeries = seriesRef.current;

        // Cleanup de séries anteriores de evidência
        if (divergenceSeriesRef.current?.length) {
            divergenceSeriesRef.current.forEach((s) => {
                try { chart?.removeSeries(s); } catch { }
            });
            divergenceSeriesRef.current = [];
        }

        if (!chart || !mainSeries) {
            if (mainSeries && typeof mainSeries.setMarkers === 'function') {
                try { mainSeries.setMarkers([]); } catch { }
            }
            return undefined;
        }

        async function renderBackendEvidences() {
            try {
                let evidenceItems = [];
                if (activeEvidenceData) {
                    evidenceItems = [activeEvidenceData];
                } else {
                    const res = await getHDFEvidences(symbol, timeframe);
                    if (!isMounted) return;
                    evidenceItems = res?.evidences || [];
                }

                // Filtrar apenas evidências prospectivas reais (excluir testes/fixtures)
                const liveItems = evidenceItems.filter((ev) => !ev.is_test && ev.source !== 'TEST');

                if (!liveItems.length) {
                    if (mainSeries && typeof mainSeries.setMarkers === 'function') {
                        try { mainSeries.setMarkers([]); } catch { }
                    }
                    return;
                }

                const candles = candlesRef.current || [];
                const parseTs = (tStr) => {
                    if (!tStr) return 0;
                    if (typeof tStr === 'number') return tStr;
                    let s = String(tStr).trim().replace(' ', 'T');
                    if (!s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) s += 'Z';
                    const d = new Date(s);
                    return isNaN(d.getTime()) ? 0 : Math.floor(d.getTime() / 1000);
                };

                const markersMap = new Map();

                liveItems.forEach((evItem) => {
                    const refTimeStr =
                        evItem.activation_time ||
                        evItem.confluence_time ||
                        evItem.pivot_2_time ||
                        evItem.detected_at ||
                        evItem.metadata?.pivot_2_time;

                    let tRef = parseTs(refTimeStr);

                    if (candles.length > 0 && tRef > 0) {
                        let closest = candles[0].time;
                        let minDiff = Math.abs(closest - tRef);
                        for (let i = 1; i < candles.length; i++) {
                            const diff = Math.abs(candles[i].time - tRef);
                            if (diff < minDiff) {
                                minDiff = diff;
                                closest = candles[i].time;
                            }
                        }
                        tRef = closest;
                    }

                    if (tRef > 0) {
                        const isBull = evItem.direction === 'BULLISH';
                        const isActivated =
                            evItem.variant_stage === 'HDF_DVP' ||
                            evItem.current_state === 'ACTIVATED' ||
                            evItem.status_code === 'ACTIVATED' ||
                            evItem.activated === true;
                        const isArmed =
                            evItem.armed === true ||
                            evItem.current_state === 'ARMED' ||
                            evItem.status_code === 'ARMED';

                        const color = isBull
                            ? (isActivated ? '#21d68d' : '#72f2b8')
                            : (isActivated ? '#ff5f72' : '#ff9f43');

                        const text = isActivated ? 'HDF' : (isArmed ? 'ARMED' : 'HDF');

                        markersMap.set(tRef, {
                            time: tRef,
                            position: isBull ? 'belowBar' : 'aboveBar',
                            color,
                            shape: isBull ? 'arrowUp' : 'arrowDown',
                            text,
                        });
                    }
                });

                const sortedMarkers = Array.from(markersMap.values())
                    .sort((a, b) => a.time - b.time)
                    .slice(-10);

                if (mainSeries && typeof mainSeries.setMarkers === 'function') {
                    try { mainSeries.setMarkers(sortedMarkers); } catch { }
                }

                if (activeEvidenceData && sortedMarkers.length > 0 && chart.timeScale) {
                    try {
                        chart.timeScale().scrollToPosition(0, true);
                    } catch {}
                }
            } catch (err) {
                console.error('Erro ao renderizar marcadores visuais HDF:', err);
            }
        }

        renderBackendEvidences();

        return () => {
            isMounted = false;
        };
    }, [activeEvidenceData, symbol, timeframe, showRSI, loading]);

    // Atualização dinâmica dos indicadores do usuário (Fase 3C)
    useEffect(() => {
        const chart = chartRef.current;
        if (!chart) return;

        const candles = candlesRef.current || [];
        const activeMap = new Map();

        // 1. Processar cada indicador ativo do usuário
        (userIndicators || []).forEach((ind) => {
            if (!ind.visible || !ind.instanceId) return;

            activeMap.set(ind.instanceId, true);

            let data = [];
            if (ind.type === 'ema') {
                data = calculateEMA(candles, ind.period);
            } else if (ind.type === 'rsi') {
                data = calculateRSI(candles, ind.period);
            }

            if (userIndicatorSeriesRef.current.has(ind.instanceId)) {
                const s = userIndicatorSeriesRef.current.get(ind.instanceId);
                s.setData(data);
                s.applyOptions({ color: ind.color });
            } else {
                const title = `${ind.type.toUpperCase()} ${ind.period}`;
                const options = {
                    color: ind.color,
                    lineWidth: 2,
                    priceLineVisible: false,
                    lastValueVisible: true,
                    title,
                };
                // User indicator RSI: adicionar no pane 1 nativo via paneIndex
                const paneIndex = ind.type === 'rsi' ? 1 : 0;
                const s = chart.addSeries(LineSeries, options, paneIndex);
                s.setData(data);

                if (ind.type === 'rsi') {
                    // Adicionar níveis 70, 50, 30 discretos sem badges coloridos
                    try {
                        s.createPriceLine({ price: 70, color: 'rgba(244,63,94,0.35)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                        s.createPriceLine({ price: 50, color: 'rgba(148,163,184,0.25)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                        s.createPriceLine({ price: 30, color: 'rgba(16,185,129,0.35)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                    } catch { }
                }

                userIndicatorSeriesRef.current.set(ind.instanceId, s);
            }
        });

        // 2. Remover séries de indicadores desativados ou excluídos
        for (const [id, s] of userIndicatorSeriesRef.current.entries()) {
            if (!activeMap.has(id)) {
                try {
                    chart.removeSeries(s);
                } catch { }
                userIndicatorSeriesRef.current.delete(id);
            }
        }

        // 3. Cálculo e renderização do RSI 14 no PANE 1 nativo (Criação/Recolhimento dinâmico sem alteração de viewport)
        const savedLogicalRange = chart.timeScale().getVisibleLogicalRange();

        if (!showRSI) {
            if (rsiSeriesRef.current) {
                try {
                    chart.removeSeries(rsiSeriesRef.current);
                } catch { }
                rsiSeriesRef.current = null;
            }
            if (divergenceSeriesRef.current && divergenceSeriesRef.current.length > 0) {
                divergenceSeriesRef.current.forEach((s) => {
                    try { chart.removeSeries(s); } catch { }
                });
                divergenceSeriesRef.current = [];
            }
        } else {
            if (!rsiSeriesRef.current) {
                try {
                    const newRsi = chart.addSeries(LineSeries, {
                        color: '#38bdf8',
                        lineWidth: 2,
                        priceLineVisible: false,
                        lastValueVisible: true,
                    }, 1);
                    newRsi.createPriceLine({ price: 70, color: 'rgba(244, 63, 94, 0.35)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                    newRsi.createPriceLine({ price: 50, color: 'rgba(148, 163, 184, 0.25)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                    newRsi.createPriceLine({ price: 30, color: 'rgba(16, 185, 129, 0.35)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                    rsiSeriesRef.current = newRsi;

                    const panes = chart.panes();
                    if (panes.length > 1) {
                        panes[0].setStretchFactor(3);
                        panes[1].setStretchFactor(1);
                    }
                } catch { }
            }
            if (rsiSeriesRef.current && candles.length > 0) {
                const rsiData = calculateRSI(candles, 14);
                rsiSeriesRef.current.setData(rsiData);
            }
        }

        if (savedLogicalRange) {
            try {
                chart.timeScale().setVisibleLogicalRange(savedLogicalRange);
            } catch { }
        }
    }, [userIndicators, symbol, timeframe, showRSI, activeEvidenceData, showDivergencesToggle, loading]);


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

            {/* Legenda Compacta do Price Pane (sobreposições EMA) */}
            {overlayIndicators.length > 0 && (
                <div className="market-chart-indicator-legend price-pane">
                    <button
                        type="button"
                        className="indicator-legend-toggle-btn"
                        onClick={() => setLegendCollapsedPrice((c) => !c)}
                        title={legendCollapsedPrice ? 'Expandir legenda de preço' : 'Recolher legenda de preço'}
                    >
                        {legendCollapsedPrice ? '▸' : '▾'} Preço ({overlayIndicators.length})
                    </button>

                    {!legendCollapsedPrice && (
                        <div className="indicator-legend-list">
                            {overlayIndicators.map((ind) => (
                                <div key={ind.instanceId} className="indicator-legend-item">
                                    <span
                                        className="indicator-legend-dot"
                                        style={{ backgroundColor: ind.color }}
                                    />
                                    <span className="indicator-legend-name">
                                        {ind.type.toUpperCase()} {ind.period}
                                    </span>
                                    <button
                                        type="button"
                                        className="indicator-legend-action-btn"
                                        onClick={() => onToggleIndicatorVisibility && onToggleIndicatorVisibility(ind.instanceId)}
                                        title={ind.visible ? 'Ocultar indicador' : 'Exibir indicador'}
                                    >
                                        {ind.visible ? '👁' : '🙈'}
                                    </button>
                                    <button
                                        type="button"
                                        className="indicator-legend-action-btn"
                                        onClick={() => onOpenIndicatorSettings && onOpenIndicatorSettings(ind)}
                                        title="Configurações do indicador"
                                    >
                                        ⚙
                                    </button>
                                    <button
                                        type="button"
                                        className="indicator-legend-action-btn remove"
                                        onClick={() => onRemoveIndicator && onRemoveIndicator(ind.instanceId)}
                                        title="Remover indicador"
                                    >
                                        ×
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Legenda Compacta do RSI Pane (oscilador RSI) */}
            {hasVisibleRSI && oscillatorIndicators.length > 0 && (
                <div className="market-chart-indicator-legend rsi-pane">
                    <button
                        type="button"
                        className="indicator-legend-toggle-btn"
                        onClick={() => setLegendCollapsedRSI((c) => !c)}
                        title={legendCollapsedRSI ? 'Expandir legenda RSI' : 'Recolher legenda RSI'}
                    >
                        {legendCollapsedRSI ? '▸' : '▾'} RSI ({oscillatorIndicators.length})
                    </button>

                    {!legendCollapsedRSI && (
                        <div className="indicator-legend-list">
                            {oscillatorIndicators.map((ind) => (
                                <div key={ind.instanceId} className="indicator-legend-item">
                                    <span
                                        className="indicator-legend-dot"
                                        style={{ backgroundColor: ind.color }}
                                    />
                                    <span className="indicator-legend-name">
                                        {ind.type.toUpperCase()} {ind.period}
                                    </span>
                                    <button
                                        type="button"
                                        className="indicator-legend-action-btn"
                                        onClick={() => onToggleIndicatorVisibility && onToggleIndicatorVisibility(ind.instanceId)}
                                        title={ind.visible ? 'Ocultar indicador' : 'Exibir indicador'}
                                    >
                                        {ind.visible ? '👁' : '🙈'}
                                    </button>
                                    <button
                                        type="button"
                                        className="indicator-legend-action-btn"
                                        onClick={() => onOpenIndicatorSettings && onOpenIndicatorSettings(ind)}
                                        title="Configurações do indicador"
                                    >
                                        ⚙
                                    </button>
                                    <button
                                        type="button"
                                        className="indicator-legend-action-btn remove"
                                        onClick={() => onRemoveIndicator && onRemoveIndicator(ind.instanceId)}
                                        title="Remover indicador"
                                    >
                                        ×
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Control de visibilidade de Divergências HDF */}
            {showRSI && activeEvidenceData && (
                <div style={{ position: 'absolute', bottom: '60px', left: '16px', zIndex: 10 }}>
                    <button
                        type="button"
                        className={`hk-toggle-btn ${showDivergencesToggle ? 'on' : 'off'}`}
                        style={{ padding: '4px 10px', fontSize: '11px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}
                        onClick={() => setShowDivergencesToggle((prev) => !prev)}
                        title="Alternar visibilidade dos segmentos de divergência HDF no gráfico e no RSI"
                    >
                        <span>Divergências</span>
                        <span>{showDivergencesToggle ? '👁' : '🙈'}</span>
                    </button>
                </div>
            )}

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

            {/* Evidence Mode - mostra somente o evento ativo, não histórico acumulado */}
            {activeEvidenceEventId && activeEvidenceData && (
                <div className="evidence-mode-overlay">
                    <div className="evidence-mode-header">
                        <span className="evidence-mode-badge">EVIDENCE MODE</span>
                        <strong className="evidence-mode-title">
                            {activeEvidenceData.symbol} • {activeEvidenceData.timeframe} • {activeEvidenceData.direction === 'BULLISH' ? '🔺 Alta' : '🔻 Baixa'}
                        </strong>
                        <button
                            type="button"
                            className="evidence-mode-close"
                            onClick={() => onClearEvidence && onClearEvidence()}
                            aria-label="Fechar Evidence Mode"
                        >
                            FECHAR EVIDÊNCIA ×
                        </button>
                    </div>
                    <div className="evidence-mode-levels">
                        {activeEvidenceData.activation_level > 0 && (
                            <span className="evidence-level-item activation">Ativação: {activeEvidenceData.activation_level?.toFixed(5)}</span>
                        )}
                        {activeEvidenceData.initial_stop > 0 && (
                            <span className="evidence-level-item stop">Stop: {activeEvidenceData.initial_stop?.toFixed(5)}</span>
                        )}
                        {activeEvidenceData.target_2R > 0 && (
                            <span className="evidence-level-item target">2R: {activeEvidenceData.target_2R?.toFixed(5)}</span>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default MarketChart;