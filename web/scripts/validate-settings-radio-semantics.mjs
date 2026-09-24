import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/AccountSettings.tsx', import.meta.url), 'utf8')

function requireText(text, label) {
  if (!source.includes(text)) throw new Error(`Missing ${label}: ${text}`)
}

for (const obsolete of ['role="radiogroup"', 'role="radio"', 'aria-checked=']) {
  if (source.includes(obsolete)) {
    throw new Error(`Settings must use native form semantics instead of ${obsolete}`)
  }
}

requireText('<fieldset className="settings-radio-fieldset">', 'native measurement radio fieldset')
requireText('<legend>Measurement units</legend>', 'measurement group label')
requireText('type="radio"', 'native measurement radio inputs')
requireText('name="measurement-units"', 'shared measurement radio name')
requireText("checked={units === 'us_customary'}", 'US checked state')
requireText("checked={units === 'metric'}", 'metric checked state')
requireText("onChange={() => void changeUnits('us_customary')}", 'US radio change handler')
requireText("onChange={() => void changeUnits('metric')}", 'metric radio change handler')

requireText('className="panel settings-panel settings-span-all settings-accessibility"', 'compact accessibility panel')
requireText('className="settings-accessibility-row"', 'compact accessibility row')
requireText('aria-label="Text size"', 'text-size select accessible name')
requireText('value={textScale}', 'text-size selected value')
requireText('TEXT_SCALE_OPTIONS.map((option)', 'text-size option source')
requireText('changeTextScale(Number(event.target.value) as TextScalePercent)', 'text-size select change handler')

if (source.includes('name="text-size"') || source.includes('settings-text-scale-grid')) {
  throw new Error('Text-size accessibility control must remain compact instead of returning to the card/radio grid.')
}

const nativeRadioCount = (source.match(/type="radio"/g) ?? []).length
if (nativeRadioCount !== 2) {
  throw new Error(`Expected exactly two measurement-unit radio inputs; found ${nativeRadioCount}.`)
}

console.log('Settings compact-accessibility and native measurement semantics passed.')
