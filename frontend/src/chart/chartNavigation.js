export function createVerticalNavigation({
    container,
    chart,
    saveCurrentView,
}) {
    let activeDragPane = null; // null | 0 | 1
    let dragStartY = 0;
    let dragStartRange = null;

    const handlePointerDown = (event) => {
        if (event.button !== 0 || !container || !chart) {
            return;
        }

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

        // Se o ponteiro estiver na coluna do eixo vertical direito (Price scale)
        if (pointerX >= priceScaleStart) {
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
            if (!targetScale) return;

            activeDragPane = paneIndex;
            dragStartY = event.clientY;
            dragStartRange = typeof targetScale.getVisibleRange === 'function' ? targetScale.getVisibleRange() : null;

            console.log('[RSI SCALE DRAG START]', {
                pointerX,
                pointerY,
                pane0Height,
                detectedPane: paneIndex,
                targetScale: `pane_${paneIndex}`,
                dragStartRange,
            });

            if (dragStartRange && typeof targetScale.setAutoScale === 'function') {
                targetScale.setAutoScale(false);
                try {
                    container.setPointerCapture?.(event.pointerId);
                } catch {}
            }
        }
    };

    const handlePointerMove = (event) => {
        if (activeDragPane === null || !dragStartRange || !chart || !container) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        const deltaY = event.clientY - dragStartY;
        const rect = container.getBoundingClientRect();

        let paneHeight = rect.height * 0.75;
        try {
            const panes = chart.panes();
            if (panes && panes[activeDragPane] && typeof panes[activeDragPane].getHeight === 'function') {
                paneHeight = panes[activeDragPane].getHeight();
            }
        } catch {}

        const rangeSize = dragStartRange.to - dragStartRange.from;
        if (!Number.isFinite(rangeSize) || rangeSize <= 0 || paneHeight <= 0) {
            return;
        }

        const priceMovement = (deltaY / paneHeight) * rangeSize;
        const targetScale = chart.priceScale('right', activeDragPane);

        if (targetScale && typeof targetScale.setVisibleRange === 'function') {
            targetScale.setVisibleRange({
                from: dragStartRange.from + priceMovement,
                to: dragStartRange.to + priceMovement,
            });
        }

        if (typeof saveCurrentView === 'function') {
            requestAnimationFrame(() => {
                saveCurrentView();
            });
        }
    };

    const finishVerticalDrag = (event) => {
        if (activeDragPane !== null) {
            try {
                if (container.hasPointerCapture?.(event.pointerId)) {
                    container.releasePointerCapture(event.pointerId);
                }
            } catch {}

            activeDragPane = null;
            dragStartRange = null;

            if (typeof saveCurrentView === 'function') {
                requestAnimationFrame(() => {
                    saveCurrentView();
                });
            }
        }
    };

    return {
        handlePointerDown,
        handlePointerMove,
        finishVerticalDrag,
    };
}