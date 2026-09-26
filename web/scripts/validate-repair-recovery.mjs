import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/repair-client.ts', import.meta.url), 'utf8')

function requirePattern(pattern, message) {
  if (!pattern.test(source)) throw new Error(message)
}

requirePattern(
  /SERVER_WRITE_STATE_UNCERTAIN\s*=\s*['"]DATABASE_WRITE_STATE_UNCERTAIN['"]/,
  'repair client must recognize the server uncertain-write code',
)
requirePattern(
  /ambiguousTransportFailure[\s\S]*SERVER_WRITE_STATE_UNCERTAIN/,
  'server uncertain-write responses must enter authoritative recovery',
)
requirePattern(
  /committedSessionMutation\(sessionId, idempotencyKey\)/,
  'session mutation recovery must use the original idempotency key',
)
requirePattern(
  /committedSessionCreation\(idempotencyKey\)/,
  'session creation recovery must use the original idempotency key',
)

const mutationBlock = source.match(
  /export async function recoverableRepairMutation[\s\S]*?(?=export async function recoverableRepairSessionCreation)/,
)?.[0]
if (!mutationBlock) throw new Error('recoverableRepairMutation implementation not found')
if ((mutationBlock.match(/newIdempotencyKey\(/g) ?? []).length !== 1) {
  throw new Error('repair mutation recovery must not mint a replacement idempotency key')
}

const creationBlock = source.match(/export async function recoverableRepairSessionCreation[\s\S]*$/)?.[0]
if (!creationBlock) throw new Error('recoverableRepairSessionCreation implementation not found')
if ((creationBlock.match(/newIdempotencyKey\(/g) ?? []).length !== 1) {
  throw new Error('repair session creation recovery must not mint a replacement idempotency key')
}

console.log('Repair uncertain-write recovery contract validated.')
