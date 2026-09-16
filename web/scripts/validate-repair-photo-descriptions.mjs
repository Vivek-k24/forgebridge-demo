import fs from 'node:fs'

const repairLog = fs.readFileSync(new URL('../src/RepairLog.tsx', import.meta.url), 'utf8')
const photoRouter = fs.readFileSync(new URL('../../api/partgraph/repair_experience/memory/router.py', import.meta.url), 'utf8')

function requireText(source, text, label) {
  if (!source.includes(text)) throw new Error(`Missing ${label}: ${text}`)
}

if (repairLog.includes('alt={`${human(photo.purpose)} repair`}')) {
  throw new Error('Repair Log must not use purpose-only generated alt text as the photo description.')
}

for (const [text, label] of [
  ["const [photoObservationId, setPhotoObservationId] = useState('')", 'optional photo-note association state'],
  ["item.source === 'user' && item.review_state === 'confirmed'", 'user-authored confirmed description filter'],
  ["body.set('observation_id', photoObservationId)", 'photo observation association'],
  ['PartGraph does not generate or guess image descriptions.', 'no-invented-description guidance'],
  ['alt={photoAltText(photo, observations)}', 'description-aware photo alt text'],
  ['Repair photo. No user-provided description is available.', 'legacy-photo fallback'],
  ['{description && <p className="repair-photo-description">{description}</p>}', 'visible user-authored description'],
]) {
  requireText(repairLog, text, label)
}

requireText(
  photoRouter,
  'observation_id: Annotated[UUID | None, Form()] = None',
  'existing nullable backend photo-observation association',
)

console.log('Repair-photo description accessibility contract passed.')
