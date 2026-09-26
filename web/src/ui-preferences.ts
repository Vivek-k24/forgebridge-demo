export type TextScalePercent = 100 | 115 | 130 | 150 | 200

export const TEXT_SCALE_OPTIONS: Array<{
  value: TextScalePercent
  label: string
  description: string
}> = [
  { value: 100, label: 'Default', description: '100% text size' },
  { value: 115, label: 'Comfortable', description: '115% text size' },
  { value: 130, label: 'Large', description: '130% text size' },
  { value: 150, label: 'Extra large', description: '150% text size' },
  { value: 200, label: 'Maximum', description: '200% text size' },
]

const TEXT_SCALE_STORAGE_KEY = 'partgraph:text-scale'
const VALID_TEXT_SCALES = new Set<number>(TEXT_SCALE_OPTIONS.map((option) => option.value))

export function readTextScale(): TextScalePercent {
  if (typeof window === 'undefined') return 100
  try {
    const stored = Number(window.localStorage.getItem(TEXT_SCALE_STORAGE_KEY))
    return VALID_TEXT_SCALES.has(stored) ? stored as TextScalePercent : 100
  } catch {
    return 100
  }
}

export function applyTextScale(scale: TextScalePercent, persist = true): void {
  if (typeof document !== 'undefined') {
    document.documentElement.style.fontSize = `${scale}%`
    document.documentElement.dataset.textScale = String(scale)
  }
  if (persist && typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(TEXT_SCALE_STORAGE_KEY, String(scale))
    } catch {
      // The preference still applies for the current page when storage is unavailable.
    }
  }
}

export function initializeUiPreferences(): void {
  applyTextScale(readTextScale(), false)
}
