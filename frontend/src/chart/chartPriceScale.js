export function zoomPriceScale(
    priceScale,
    visibleRange,
    deltaY,
    zoomFactor = 0.12
) {
    if (!priceScale) return;
    const range = visibleRange || (typeof priceScale.getVisibleRange === 'function' ? priceScale.getVisibleRange() : null);
    if (!range) return;

    const size = range.to - range.from;
    if (!Number.isFinite(size) || size <= 0) return;

    const factor = deltaY < 0 ? (1 - zoomFactor) : (1 + zoomFactor);
    const newSize = size * factor;
    const center = (range.from + range.to) / 2;

    try {
        if (typeof priceScale.setAutoScale === 'function') {
            priceScale.setAutoScale(false);
        }
        if (typeof priceScale.setVisibleRange === 'function') {
            priceScale.setVisibleRange({
                from: center - newSize / 2,
                to: center + newSize / 2,
            });
        }
    } catch (e) {
        console.error('[ZOOM PRICE SCALE ERROR]', e);
    }
}

export function resetPriceScale(priceScale) {
    if (priceScale && typeof priceScale.setAutoScale === 'function') {
        priceScale.setAutoScale(true);
    }
}

export function createPriceScaleWheelHandler({
    container,
    chart,
    saveCurrentView,
}) {
    return function handlePriceScaleWheel(event) {
        if (!container || !chart) return;

        const rect = container.getBoundingClientRect();
        const pointerX = event.clientX - rect.left;
        const pointerY = event.clientY - rect.top;

        let priceScaleWidth = 55;
        try {
            const scale0 = chart.priceScale('right', 0);
            if (scale0 && typeof scale0.width === 'function') {
                priceScaleWidth = Math.max(scale0.width(), 45);
            }
        } catch {}

        const priceScaleStart = rect.width - priceScaleWidth;

        // Executar zoom no eixo vertical apenas se o mouse estiver sobre a coluna da escala direita
        if (pointerX < priceScaleStart) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === 'function') {
            event.stopImmediatePropagation();
        }

        // Hit test por coordenada Y para determinar em qual Pane o ponteiro está
        let paneIndex = 0;
        let pane0Height = rect.height * 0.75;
        try {
            const panes = chart.panes();
            if (panes && panes.length > 1 && typeof panes[0].getHeight === 'function') {
                pane0Height = panes[0].getHeight();
            }
        } catch {}

        if (pointerY >= pane0Height) {
            paneIndex = 1;
        }

        const targetScale = chart.priceScale('right', paneIndex);

        console.log('[RSI SCALE DEBUG]', {
            pointerX,
            pointerY,
            pane0Height,
            detectedPane: paneIndex,
            targetScale: `pane_${paneIndex}`,
        });

        if (targetScale) {
            const range = typeof targetScale.getVisibleRange === 'function' ? targetScale.getVisibleRange() : null;
            zoomPriceScale(targetScale, range, event.deltaY);
        }

        if (typeof saveCurrentView === 'function') {
            requestAnimationFrame(() => {
                saveCurrentView();
            });
        }
    };
}