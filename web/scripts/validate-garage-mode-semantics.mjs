import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/GarageWorkspace.tsx', import.meta.url), 'utf8')

function requireText(text, label) {
  if (!source.includes(text)) throw new Error(`Missing ${label}: ${text}`)
}

if (source.includes('role="tablist"')) {
  throw new Error('Garage add-mode switch must not advertise tablist semantics without implementing the tab pattern.')
}

requireText('className="segmented" role="group" aria-label="Add vehicle method"', 'labeled mode button group')
requireText("aria-pressed={mode === 'manual'}", 'manual-mode toggle state')
requireText("aria-pressed={mode === 'vin'}", 'VIN-mode toggle state')

console.log('Garage add-mode semantic contract passed.')
