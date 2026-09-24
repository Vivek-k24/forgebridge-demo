import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/offline-repair.ts', import.meta.url), 'utf8')

const required = [
  "const PACK_KEY = 'partgraph:offline-repair-pack:v2'",
  "const LEGACY_PACK_KEY = 'partgraph:offline-repair-pack:v1'",
  "const LEGACY_OWNER_KEY = 'partgraph:offline-owner:v1'",
  'const { owner_id: _ownerId, ...offlinePack } = pack',
  'target?.removeItem(LEGACY_OWNER_KEY)',
  'pack.owner_id !== undefined',
  'pack.email !== undefined',
  'pack.username !== undefined',
]

for (const marker of required) {
  if (!source.includes(marker)) {
    throw new Error(`Offline privacy contract missing marker: ${marker}`)
  }
}

const forbidden = [
  'export type OfflineOwner',
  'rememberOfflineOwner',
  'cachedOfflineOwner',
  'hasOfflineRepairPackForOwner',
  'email: string; username: string',
]

for (const marker of forbidden) {
  if (source.includes(marker)) {
    throw new Error(`Offline privacy contract contains forbidden identity cache marker: ${marker}`)
  }
}

console.log('Offline repair cache privacy contract passed.')
