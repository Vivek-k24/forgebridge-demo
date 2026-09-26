import fs from 'node:fs'

const shell = fs.readFileSync(new URL('../src/PartGraphShell.tsx', import.meta.url), 'utf8')
const css = fs.readFileSync(new URL('../src/partgraph-shell.css', import.meta.url), 'utf8')

function requireText(source, text, label) {
  if (!source.includes(text)) throw new Error(`Missing ${label}: ${text}`)
}

for (const [text, label] of [
  ['const PAGE_TITLES: Record<PageKey, string>', 'route-specific title map'],
  ['document.title = `${PAGE_TITLES[page]} | PartGraph`', 'document-title update'],
  ['const mainContentRef = useRef<HTMLDivElement>(null)', 'main-content focus ref'],
  ["querySelector<HTMLElement>('h1')", 'new-view heading focus target'],
  ["focus({ preventScroll: true })", 'route focus without implicit scrolling'],
  ["matchMedia('(prefers-reduced-motion: reduce)')", 'reduced-motion route behavior'],
  ["behavior: reducedMotion ? 'auto' : 'smooth'", 'motion-aware scroll policy'],
  ['className="partgraph-skip-link"', 'skip link'],
  ['href="#partgraph-main-content"', 'skip-link target'],
  ['id="partgraph-main-content"', 'main-content target id'],
  ['tabIndex={-1}', 'programmatic focus target'],
]) {
  requireText(shell, text, label)
}

if (shell.includes("window.scrollTo({ top: 0, behavior: 'smooth' })")) {
  throw new Error('navigate() must not force unconditional smooth scrolling.')
}

requireText(css, '.partgraph-skip-link:focus', 'visible skip-link focus state')
requireText(css, '.partgraph-main-content', 'main-content scroll-margin styling')

console.log('SPA navigation accessibility contract passed.')
