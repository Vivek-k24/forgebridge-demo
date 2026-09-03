import { useEffect, useRef, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react'

type YearWheelProps = {
  value: number
  min: number
  max: number
  onChange: (year: number) => void
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

export function YearWheel({ value, min, max, onChange }: YearWheelProps) {
  const wheelRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ pointerId: number; startY: number; startValue: number } | null>(null)

  useEffect(() => {
    const node = wheelRef.current
    if (!node) return

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault()
      if (Math.abs(event.deltaY) < 2) return
      const direction = event.deltaY > 0 ? -1 : 1
      const steps = Math.max(1, Math.min(3, Math.round(Math.abs(event.deltaY) / 80)))
      onChange(clamp(value + (direction * steps), min, max))
    }

    node.addEventListener('wheel', handleWheel, { passive: false })
    return () => node.removeEventListener('wheel', handleWheel)
  }, [max, min, onChange, value])

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    let next = value
    if (event.key === 'ArrowUp') next = value + 1
    else if (event.key === 'ArrowDown') next = value - 1
    else if (event.key === 'Home') next = max
    else if (event.key === 'End') next = min
    else return

    event.preventDefault()
    onChange(clamp(next, min, max))
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    dragRef.current = { pointerId: event.pointerId, startY: event.clientY, startValue: value }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    const rows = Math.round((event.clientY - drag.startY) / 42)
    onChange(clamp(drag.startValue + rows, min, max))
  }

  function clearPointer(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null
  }

  const offsets = [2, 1, 0, -1, -2]

  return (
    <div
      ref={wheelRef}
      className="year-wheel"
      role="spinbutton"
      tabIndex={0}
      aria-label="Model year"
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-valuetext={String(value)}
      onKeyDown={handleKeyDown}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={clearPointer}
      onPointerCancel={clearPointer}
    >
      <span className="year-wheel__selection" aria-hidden="true" />
      {offsets.map((offset) => {
        const candidate = value + offset
        const unavailable = candidate < min || candidate > max
        return (
          <button
            type="button"
            key={offset}
            className={`year-wheel__item year-wheel__item--${Math.abs(offset)}`}
            disabled={unavailable}
            aria-current={offset === 0 ? 'true' : undefined}
            onClick={() => {
              if (!unavailable) onChange(candidate)
            }}
          >
            {candidate}
          </button>
        )
      })}
    </div>
  )
}
