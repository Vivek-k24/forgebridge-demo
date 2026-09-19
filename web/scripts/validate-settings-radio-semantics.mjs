import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/AccountSettings.tsx', import.meta.url), 'utf8')

function requireText(text, label) {
  if (!source.includes(text)) throw new Error(`Missing ${label}: ${text}`)
}

for (const obsolete of ['role="radiogroup"', 'role="radio"', 'aria-checked=']) {
  if (source.includes(obsolete)) {
    throw new Error(`Settings must use native radio semantics instead of ${obsolete}`)
  }
}

requireText('<fieldset className="settings-radio-fieldset">', 'native radio fieldsets')
requireText('<legend>Measurement units</legend>', 'measurement group label')
requireText('<legend>Text size</legend>', 'text-size group label')
requireText('type="radio"', 'native radio inputs')
requireText('name="measurement-units"', 'shared measurement radio name')
requireText('name="text-size"', 'shared text-size radio name')
requireText("checked={units === 'us_customary'}", 'US checked state')
requireText("checked={units === 'metric'}", 'metric checked state')
requireText('checked={textScale === option.value}', 'text-size checked state')
requireText("onChange={() => void changeUnits('us_customary')}", 'US radio change handler')
requireText("onChange={() => void changeUnits('metric')}", 'metric radio change handler')
requireText('onChange={() => changeTextScale(option.value)}', 'text-size radio change handler')

const nativeRadioCount = (source.match(/type="radio"/g) ?? []).length
if (nativeRadioCount < 3) {
  throw new Error(`Expected native radio inputs for both groups; found ${nativeRadioCount}.`)
}

console.log('Settings native-radio semantic contract passed.')
