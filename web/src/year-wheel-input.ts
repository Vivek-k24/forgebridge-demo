export function installYearWheelInputSupport(): () => void {
  function focusHoveredYearWheel(event: globalThis.WheelEvent) {
    const target = event.target
    if (!(target instanceof Element)) return

    const wheel = target.closest<HTMLElement>('.year-wheel')
    if (!wheel) return

    // The YearWheel component intentionally consumes wheel input only while
    // focused so normal page scrolling is not hijacked. A wheel gesture that
    // originates over the control is an equally explicit interaction, so move
    // focus there before React's onWheel handler runs.
    wheel.focus({ preventScroll: true })
  }

  document.addEventListener('wheel', focusHoveredYearWheel, { capture: true, passive: true })
  return () => document.removeEventListener('wheel', focusHoveredYearWheel, { capture: true })
}
