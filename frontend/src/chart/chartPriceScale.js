export function zoomPriceScale(
    priceScale,
    visibleRange,
    deltaY,
    zoomFactor = 0.12
) {
    if (!visibleRange) return;

    const size = visibleRange.to - visibleRange.from;

    const factor =
        deltaY < 0
            ? (1 - zoomFactor)
            : (1 + zoomFactor);

    const newSize = size * factor;

    const center =
        (visibleRange.from + visibleRange.to) / 2;

    priceScale.setAutoScale(false);

    priceScale.setVisibleRange({
        from: center - newSize / 2,
        to: center + newSize / 2,
    });
}

export function resetPriceScale(priceScale) {
    priceScale.setAutoScale(true);
}
export function createPriceScaleWheelHandler({
    container,
    priceScale,
    saveCurrentView,
}) {
    return function handlePriceScaleWheel(event) {
        const rect = container.getBoundingClientRect();
        const priceScaleWidth = priceScale.width();

        const pointerX = event.clientX - rect.left;
        const priceScaleStart = rect.width - priceScaleWidth;

        if (
            priceScaleWidth <= 0 ||
            pointerX < priceScaleStart
        ) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        zoomPriceScale(
            priceScale,
            priceScale.getVisibleRange(),
            event.deltaY,
        );

        requestAnimationFrame(() => {
            saveCurrentView();
        });
    };
}