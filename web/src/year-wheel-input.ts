export function installYearWheelInputSupport(): () => void {
  function captureHoveredYearWheel(event: globalThis.WheelEvent) {
    const target = event.target
    if (!(target instanceof Element)) return

    const wheel = target.closest<HTMLElement>('.year-wheel')
    if (!wheel) return

    // A wheel/trackpad gesture that starts over the year control belongs to the
    // control, not the document. Focus it before React handles the same event,
    // then suppress the browser's page scroll so one gesture cannot move both
    // the selected year and the surrounding screen.
    wheel.focus({ preventScroll: true })
    event.preventDefault()
  }

  document.addEventListener('wheel', captureHoveredYearWheel, { capture: true, passive: false })
  return () => document.removeEventListener('wheel', captureHoveredYearWheel, { capture: true })
}
