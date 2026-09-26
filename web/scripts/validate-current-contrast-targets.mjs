import fs from 'node:fs'

const css = fs.readFileSync(new URL('../src/accessibility-ui.css', import.meta.url), 'utf8')
const main = fs.readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8')

function fail(message) {
  throw new Error(`UI-010 accessibility contract failed: ${message}`)
}

function readCustomProperty(name) {
  const match = css.match(new RegExp(`${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*:\\s*([^;]+);`))
  if (!match) fail(`missing ${name}`)
  return match[1].trim()
}

function channel(value) {
  const normalized = value / 255
  return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4
}

function luminance(hex) {
  const match = /^#([0-9a-f]{6})$/i.exec(hex)
  if (!match) fail(`expected six-digit hex color, got ${hex}`)
  const raw = match[1]
  const red = channel(Number.parseInt(raw.slice(0, 2), 16))
  const green = channel(Number.parseInt(raw.slice(2, 4), 16))
  const blue = channel(Number.parseInt(raw.slice(4, 6), 16))
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

function contrast(foreground, background) {
  const first = luminance(foreground)
  const second = luminance(background)
  const lighter = Math.max(first, second)
  const darker = Math.min(first, second)
  return (lighter + 0.05) / (darker + 0.05)
}

const muted = readCustomProperty('--pg-dark-muted-text')
for (const background of ['#0f1a20', '#132126', '#16262b']) {
  const ratio = contrast(muted, background)
  if (ratio < 4.5) fail(`${muted} on ${background} is only ${ratio.toFixed(2)}:1`)
}

const target = readCustomProperty('--pg-primary-touch-target')
const targetMatch = /^(\d+(?:\.\d+)?)px$/.exec(target)
if (!targetMatch) fail(`primary target must be expressed in px, got ${target}`)
if (Number(targetMatch[1]) < 44) fail(`primary target must remain at least 44px, got ${target}`)

for (const required of [
  '.repair-workspace-shell input::placeholder',
  '.partgraph-main .home-metrics small',
  '.partgraph-main .home-repair-main p',
  '.partgraph-main .home-repair-meta > span',
  '.partgraph-main .home-action-stack span',
  '.partgraph-main .home-trust-panel p:last-child',
  '.partgraph-main .equipment-mic',
]) {
  if (!css.includes(required)) fail(`missing audited selector ${required}`)
}

const lightIndex = main.indexOf("import './light-panel-contrast.css'")
const accessibilityIndex = main.indexOf("import './accessibility-ui.css'")
if (lightIndex < 0 || accessibilityIndex < 0 || accessibilityIndex <= lightIndex) {
  fail('accessibility-ui.css must remain loaded after light-panel-contrast.css')
}

console.log(`UI-010 current contrast/target contract passed: muted minimum ${Math.min(...['#0f1a20', '#132126', '#16262b'].map((background) => contrast(muted, background))).toFixed(2)}:1, primary target ${target}.`)
