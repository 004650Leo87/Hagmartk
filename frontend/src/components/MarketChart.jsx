import { useEffect, useRef, useState } from 'react';

import { getCandles } from '../services/api';

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
}) {
    const containerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);

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

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [candleCount, setCandleCount] = useState(0);


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
        } = createMarketChart(container);

        chartRef.current = chart;
        seriesRef.current = series;

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

            chart.remove();

            chartRef.current = null;
            seriesRef.current = null;
            saveCurrentViewRef.current = null;
        };
    }, []);


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

        viewportRestoredRef.current = false;

        async function loadCandles() {
            try {
                setError('');

                const {
                    candles,
                } = await fetchChartCandles({
                    getCandles,
                    symbol,
                    timeframe,
                    limit: HISTORY_PAGE_SIZE,
                });

                if (!active) {
                    return;
                }

                const chart = chartRef.current;
                const series = seriesRef.current;

                if (!chart || !series) {
                    return;
                }

                setCandleCount(candles.length);

                if (candles.length === 0) {
                    setError(
                        `Nenhum candle válido foi recebido para ${symbol} ${timeframe}.`,
                    );

                    return;
                }

                /*
                 * Atualiza os candles sem executar fitContent.
                 *
                 * Nas atualizações seguintes, o viewport
                 * permanece exatamente onde o usuário deixou.
                 */
                series.setData(candles);

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
                             * Confirma que essa restauração ainda
                             * pertence à tela atual.
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
        setCandleCount(0);

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

            <div className="market-chart-diagnostic">
                {candleCount > 0
                    ? `${candleCount} candles carregados`
                    : 'Aguardando candles'}
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
        </div>
    );
}

export default MarketChart;