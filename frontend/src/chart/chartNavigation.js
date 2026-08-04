export function createVerticalNavigation({
    container,
    priceScale,
    series,
    saveCurrentView,
}) {
    let verticalDragActive = false;
    let verticalDragDetected = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let dragStartRange = null;

    const handlePointerDown = (event) => {
        if (event.button !== 0) {
            return;
        }

        const priceScaleWidth = priceScale.width();
        const chartAreaWidth =
            container.clientWidth - priceScaleWidth;

        if (event.offsetX >= chartAreaWidth) {
            return;
        }

        dragStartX = event.clientX;
        dragStartY = event.clientY;
        dragStartRange = priceScale.getVisibleRange();

        verticalDragActive = Boolean(dragStartRange);
        verticalDragDetected = false;
    };

    const handlePointerMove = (event) => {
        if (!verticalDragActive || !dragStartRange) {
            return;
        }

        const deltaX = event.clientX - dragStartX;
        const deltaY = event.clientY - dragStartY;

        if (!verticalDragDetected) {
            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                return;
            }

            if (Math.abs(deltaY) < 4) {
                return;
            }

            verticalDragDetected = true;
            priceScale.setAutoScale(false);
            container.setPointerCapture?.(event.pointerId);
        }

        if (!verticalDragDetected) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        const rangeSize =
            dragStartRange.to - dragStartRange.from;

        if (
            !Number.isFinite(rangeSize) ||
            rangeSize <= 0 ||
            container.clientHeight <= 0
        ) {
            return;
        }

        const priceMovement =
            (deltaY / container.clientHeight) * rangeSize;

        priceScale.setVisibleRange({
            from: dragStartRange.from + priceMovement,
            to: dragStartRange.to + priceMovement,
        });

        requestAnimationFrame(() => {
            saveCurrentView();
        });
    };

    const finishVerticalDrag = (event) => {
        if (
            verticalDragDetected &&
            container.hasPointerCapture?.(event.pointerId)
        ) {
            container.releasePointerCapture(event.pointerId);
        }

        verticalDragActive = false;
        verticalDragDetected = false;
        dragStartRange = null;

        requestAnimationFrame(() => {
            saveCurrentView();
        });
    };

    return {
        handlePointerDown,
        handlePointerMove,
        finishVerticalDrag,
    };
}