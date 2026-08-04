export function addChartEvent(target, event, handler, options = true) {
    target.addEventListener(event, handler, options);
}

export function removeChartEvent(target, event, handler, options = true) {
    target.removeEventListener(event, handler, options);
}

export function addChartEvents(target, events) {
    events.forEach(({ event, handler, options = true }) => {
        target.addEventListener(event, handler, options);
    });
}

export function removeChartEvents(target, events) {
    events.forEach(({ event, handler, options = true }) => {
        target.removeEventListener(event, handler, options);
    });
}