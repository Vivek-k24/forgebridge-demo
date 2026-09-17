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

const appCss = path.join(srcRoot, 'app.css')
if (!statSync(appCss).isFile()) {
  throw new Error('src/app.css is missing')
}

console.log('Retired frontend asset guard passed.')
