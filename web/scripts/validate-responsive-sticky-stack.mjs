import { readFileSync } from 'node:fs'

const shell = readFileSync(new URL('../src/PartGraphShell.tsx', import.meta.url), 'utf8')
const css = readFileSync(new URL('../src/partgraph-shell.css', import.meta.url), 'utf8')

const shellMarkers = [
  'useRef<HTMLDivElement>(null)',
  'useRef<HTMLElement>(null)',
  "querySelector<HTMLElement>('.account-strip')",
  "--partgraph-account-strip-height",
  "--partgraph-workspace-nav-height",
  "new ResizeObserver(updateStickyOffsets)",
  'observer?.observe(accountStrip)',
  'observer?.observe(sidebar)',
]

for (const marker of shellMarkers) {
  if (!shell.includes(marker)) {
    throw new Error(`Responsive sticky-stack contract missing runtime measurement marker: ${marker}`)
  }
}

const cssMarkers = [
  'top: var(--partgraph-account-strip-height, 46px);',
  'top: calc(var(--partgraph-account-strip-height, 46px) + var(--partgraph-workspace-nav-height, 50px));',
]

for (const marker of cssMarkers) {
  if (!css.includes(marker)) {
    throw new Error(`Responsive sticky-stack contract missing measured CSS offset: ${marker}`)
  }
}

const forbidden = [
  'top: 96px;',
  'top: 98px;',
]

for (const marker of forbidden) {
  if (css.includes(marker)) {
    throw new Error(`Responsive sticky-stack contract contains obsolete fixed offset: ${marker}`)
  }
}

console.log('Responsive sticky-stack measurement contract passed.')
