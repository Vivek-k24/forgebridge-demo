import { readFileSync } from 'node:fs'

const repairLog = readFileSync(new URL('../src/RepairLog.tsx', import.meta.url), 'utf8')
const garage = readFileSync(new URL('../src/GarageWorkspace.tsx', import.meta.url), 'utf8')

const requiredRepairLogNames = [
  'aria-label="Current repair"',
  'aria-label="Storage location name"',
  'aria-label="Storage location notes"',
  'aria-label="Hardware item type"',
  'aria-label="Hardware item label"',
  'aria-label="Hardware origin or position"',
  'aria-label="Observation category"',
  'aria-label="Observation details"',
  'aria-label="Photo purpose"',
  'aria-label="Repair photo"',
]

for (const marker of requiredRepairLogNames) {
  if (!repairLog.includes(marker)) {
    throw new Error(`Repair Log accessibility contract missing programmatic name: ${marker}`)
  }
}

const requiredGarageMarkers = [
  '<label className="garage-field-label" htmlFor="garage-model-year">',
  'id="garage-model-year"',
]

for (const marker of requiredGarageMarkers) {
  if (!garage.includes(marker)) {
    throw new Error(`Garage accessibility contract missing model-year label association: ${marker}`)
  }
}

const forbiddenGarageMarker = '<div className="garage-field-label"><span>Model year</span><small>required</small></div>'
if (garage.includes(forbiddenGarageMarker)) {
  throw new Error('Garage model year regressed to a visual-only label.')
}

console.log('Current form-control accessibility-name contract passed.')
