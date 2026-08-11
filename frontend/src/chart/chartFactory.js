import {
    CandlestickSeries,
    ColorType,
    CrosshairMode,
    LineSeries,
    LineStyle,
    createChart,
} from 'lightweight-charts';

export function createMarketChart(container) {
    const chart = createChart(container, {
        width: Math.max(container.clientWidth, 1),
        height: Math.max(container.clientHeight, 1),

        layout: {
            background: {
                type: ColorType.Solid,
                color: '#050a11',
            },
            textColor: '#8194b2',
            attributionLogo: false,
        },

        grid: {
            vertLines: {
                color: 'rgba(116, 137, 168, 0.08)',
            },
            horzLines: {
                color: 'rgba(116, 137, 168, 0.08)',
            },
        },

        localization: {
            locale: 'pt-BR',
            timeFormatter: (timestamp) => {
                if (typeof timestamp !== 'number') {
                    return String(timestamp ?? '');
                }

                const MONTHS_BR = [
                    'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                    'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
                ];

                const date = new Date(timestamp * 1000);
                const day = String(date.getDate()).padStart(2, '0');
                const month = MONTHS_BR[date.getMonth()];
                const year = String(date.getFullYear()).slice(-2);
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');

                return `${day} ${month} '${year}  ${hours}:${minutes}`;
            },
        },

        crosshair: {
            mode: CrosshairMode.Normal,
            vertLine: {
                visible: true,
                labelVisible: true,
            },
            horzLine: {
                visible: true,
                labelVisible: true,
            },
        },

        rightPriceScale: {
            visible: true,
            borderColor: '#1d2a3c',
        },

        timeScale: {
            visible: true,
            timeVisible: true,
            secondsVisible: false,
            borderColor: '#1d2a3c',
            rightOffset: 8,
            barSpacing: 8,
            tickMarkFormatter: (timestamp, tickMarkType) => {
                if (typeof timestamp !== 'number') {
                    return String(timestamp ?? '');
                }

                const MONTHS_BR = [
                    'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                    'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
                ];

                const date = new Date(timestamp * 1000);
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const month = MONTHS_BR[date.getMonth()];

                // TickMarkType: 0=Year, 1=Month, 2=DayOfMonth, 3=Time, 4=TimeWithSeconds
                if (tickMarkType <= 1) {
                    return `${month} ${date.getFullYear()}`;
                }
                if (tickMarkType === 2) {
                    return `${day} ${month}`;
                }
                return `${hours}:${minutes}`;
            },
        },

        handleScroll: {
            mouseWheel: true,
            pressedMouseMove: true,
        },

        handleScale: {
            mouseWheel: true,
            pinch: true,
            axisPressedMouseMove: true,
        },
    });

    // ── PANE 0: Candlestick + EMA overlays ─────────────────────────────────
    const series = chart.addSeries(CandlestickSeries, {
        upColor: '#21d68d',
        downColor: '#ff5f72',
        borderUpColor: '#21d68d',
        borderDownColor: '#ff5f72',
        wickUpColor: '#21d68d',
        wickDownColor: '#ff5f72',
        priceLineVisible: true,
        lastValueVisible: true,
    }, 0);

    const ema50Series = chart.addSeries(LineSeries, {
        color: '#ff9800',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'EMA 50',
    }, 0);

    const ema200Series = chart.addSeries(LineSeries, {
        color: '#9c27b0',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'EMA 200',
    }, 0);

    // ── PANE 1: RSI — PANE VERDADEIRO e independente ───────────────────────
    // paneIndex = 1 cria automaticamente o segundo pane com escala própria.
    // NÃO usa priceScaleId overlay, NÃO usa scaleMargins para simular painel.
    const rsiSeries = chart.addSeries(LineSeries, {
        color: '#38bdf8',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
    }, 1);

    // Linhas de referência RSI no PANE 1 (70 / 50 / 30)
    // axisLabelVisible: false → sem badges coloridos no eixo
    rsiSeries.createPriceLine({
        price: 70,
        color: 'rgba(244, 63, 94, 0.35)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
    });

    rsiSeries.createPriceLine({
        price: 50,
        color: 'rgba(148, 163, 184, 0.25)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
    });

    rsiSeries.createPriceLine({
        price: 30,
        color: 'rgba(16, 185, 129, 0.35)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
    });

    // Configurar a price scale do PANE 1 (RSI) para ser visualmente idêntica
    // à price scale do PANE 0, mas com range fixo 0–100.
    try {
        const panes = chart.panes();
        if (panes.length > 1) {
            // Pane 0 = price (75%), Pane 1 = RSI (25%)
            panes[0].setStretchFactor(3);
            panes[1].setStretchFactor(1);
        }
    } catch { }

    // Escala RSI: mesma aparência da escala de preço (neutro, sem badges)
    try {
        chart.priceScale('right', 1).applyOptions({
            borderColor: 'rgba(148, 163, 184, 0.15)',
            autoScale: true,
            textColor: '#94A3B8',
        });
    } catch { }

    return {
        chart,
        series,
        ema50Series,
        ema200Series,
        rsiSeries,
    };
}