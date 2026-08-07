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

    const series = chart.addSeries(CandlestickSeries, {
        upColor: '#21d68d',
        downColor: '#ff5f72',
        borderUpColor: '#21d68d',
        borderDownColor: '#ff5f72',
        wickUpColor: '#21d68d',
        wickDownColor: '#ff5f72',
        priceLineVisible: true,
        lastValueVisible: true,
    });

    // Sub-séries para overlays e painel RSI
    const ema50Series = chart.addSeries(LineSeries, {
        color: '#ff9800',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'EMA 50',
    });

    const ema200Series = chart.addSeries(LineSeries, {
        color: '#9c27b0',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'EMA 200',
    });

    const rsiSeries = chart.addSeries(LineSeries, {
        color: '#29b6f6',
        lineWidth: 2,
        priceScaleId: 'rsi_scale',
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'RSI 14',
    });

    // Linhas de níveis do RSI (70, 50, 30)
    rsiSeries.createPriceLine({
        price: 70,
        color: 'rgba(255, 95, 114, 0.5)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: '70',
    });

    rsiSeries.createPriceLine({
        price: 50,
        color: 'rgba(129, 148, 178, 0.4)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: '50',
    });

    rsiSeries.createPriceLine({
        price: 30,
        color: 'rgba(33, 214, 141, 0.5)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: '30',
    });

    chart.priceScale('rsi_scale').applyOptions({
        scaleMargins: {
            top: 0.75,
            bottom: 0.03,
        },
        visible: false,
    });

    return {
        chart,
        series,
        ema50Series,
        ema200Series,
        rsiSeries,
    };
}