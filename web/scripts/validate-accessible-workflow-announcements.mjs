import fs from 'node:fs'

function read(path) {
  return fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
}

function requireText(source, text, label) {
  if (!source.includes(text)) {
    throw new Error(`Missing ${label}: ${text}`)
  }
}

const bridge = read('src/AccessibleWorkflowAnnouncements.tsx')
const main = read('src/main.tsx')
const garage = read('src/GarageWorkspace.tsx')
const repairLog = read('src/RepairLog.tsx')
const readiness = read('src/RepairMemory.tsx')
const startRepair = read('src/StartRepair.tsx')
const completion = read('src/RepairCompletion.tsx')

for (const [text, label] of [
  ['role="status"', 'polite status role'],
  ['aria-live="polite"', 'polite status live setting'],
  ['role="alert"', 'error alert role'],
  ['aria-live="assertive"', 'assertive error live setting'],
  ['aria-atomic="true"', 'atomic announcement setting'],
  ['MutationObserver', 'dynamic workflow observer'],
  ['alreadyLive(candidate)', 'duplicate-live-region suppression'],
]) {
  requireText(bridge, text, label)
}

for (const selector of [
  '.workspace-alert--success',
  '.workspace-alert--error',
  '.memory-alert--success',
  '.memory-alert--error',
  '.repair-alert--success',
  '.repair-alert--error',
]) {
  requireText(bridge, selector, `audited selector ${selector}`)
}

requireText(main, "import AccessibleWorkflowAnnouncements from './AccessibleWorkflowAnnouncements'", 'announcement bridge import')
requireText(main, '<AccessibleWorkflowAnnouncements />', 'announcement bridge mount')

requireText(garage, 'workspace-alert--success', 'Garage success surface')
requireText(garage, 'workspace-alert--error', 'Garage error surface')
requireText(repairLog, 'workspace-alert--error', 'Repair Log error surface')
requireText(readiness, 'memory-alert--success', 'Readiness success surface')
requireText(readiness, 'memory-alert--error', 'Readiness error surface')
requireText(startRepair, 'workspace-alert--error', 'Start Repair error surface')
requireText(completion, 'repair-alert--success', 'Completion success surface')
requireText(completion, 'repair-alert--error', 'Completion error surface')

console.log('Accessible workflow announcement contract passed.')
