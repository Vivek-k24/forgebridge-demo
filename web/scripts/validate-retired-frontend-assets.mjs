import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const webRoot = path.resolve(scriptDir, '..')
const srcRoot = path.join(webRoot, 'src')

const retiredFiles = [
  'src/YearWheel.tsx',
  'src/production-launch.css',
]

for (const relativePath of retiredFiles) {
  const absolutePath = path.join(webRoot, relativePath)
  if (existsSync(absolutePath)) {
    throw new Error(`Retired frontend asset returned: ${relativePath}`)
  }
}

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(absolutePath)
    if (!entry.isFile()) return []
    return /\.(?:ts|tsx|css|html)$/.test(entry.name) ? [absolutePath] : []
  })
}

const forbiddenReferences = [
  { pattern: /YearWheel/, label: 'YearWheel' },
  { pattern: /production-launch\.css/, label: 'production-launch.css' },
  { pattern: /year-wheel(?:__|\b)/, label: 'retired year-wheel selector' },
]

for (const absolutePath of sourceFiles(srcRoot)) {
  const text = readFileSync(absolutePath, 'utf8')
  for (const { pattern, label } of forbiddenReferences) {
    if (pattern.test(text)) {
      throw new Error(`${label} reference remains in ${path.relative(webRoot, absolutePath)}`)
    }
  }
}

const repairMemoryTsx = readFileSync(path.join(srcRoot, 'RepairMemory.tsx'), 'utf8')
const repairMemoryCss = readFileSync(path.join(srcRoot, 'repair-memory.css'), 'utf8')
const retiredReadinessPatterns = [
  { text: repairMemoryTsx, pattern: /memory-session-bar/, label: 'retired Readiness session bar markup' },
  { text: repairMemoryTsx, pattern: /memory-session-state/, label: 'retired Readiness session-state markup' },
  { text: repairMemoryTsx, pattern: /function\s+selectSession\b/, label: 'retired Readiness session selector handler' },
  { text: repairMemoryTsx, pattern: /function\s+acquireLease\b/, label: 'retired hidden Readiness lease handler' },
  { text: repairMemoryCss, pattern: /\.memory-session-bar\b/, label: 'retired Readiness session bar styles' },
  { text: repairMemoryCss, pattern: /\.memory-session-state\b/, label: 'retired Readiness session-state styles' },
]

for (const { text, pattern, label } of retiredReadinessPatterns) {
  if (pattern.test(text)) {
    throw new Error(`${label} returned`)
  }
}

const appCss = path.join(srcRoot, 'app.css')
if (!statSync(appCss).isFile()) {
  throw new Error('src/app.css is missing')
}

console.log('Retired frontend asset guard passed.')
