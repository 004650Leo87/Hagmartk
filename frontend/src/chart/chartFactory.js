import {
    CandlestickSeries,
    ColorType,
    CrosshairMode,
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

        crosshair: {
            mode: CrosshairMode.Normal,
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

    return {
        chart,
        series,
    };
}