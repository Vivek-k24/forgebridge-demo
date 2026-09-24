import fs from 'node:fs'

const auth = fs.readFileSync(new URL('../src/AuthGate.tsx', import.meta.url), 'utf8')
const settings = fs.readFileSync(new URL('../src/AccountSettings.tsx', import.meta.url), 'utf8')
const shell = fs.readFileSync(new URL('../src/PartGraphShell.tsx', import.meta.url), 'utf8')
const footer = fs.readFileSync(new URL('../src/SiteFooter.tsx', import.meta.url), 'utf8')

function requireText(source, text, label) {
  if (!source.includes(text)) throw new Error(`Missing ${label}: ${text}`)
}

requireText(auth, 'Password requirements', 'visible signup password requirements heading')
requireText(auth, '12–128 characters.', 'signup password length guidance')
requireText(auth, 'No uppercase, number, or symbol pattern is required.', 'password complexity truth')
requireText(auth, 'aria-describedby={mode === \'register\' ? \'password-requirements\' : undefined}', 'password accessible description')
requireText(auth, '<SiteFooter variant="dark" />', 'signed-out footer')
requireText(shell, '<SiteFooter />', 'authenticated global footer')

for (const link of ['About', 'Privacy Policy', 'Terms', 'Contact Us']) {
  requireText(footer, link, `footer ${link} link`)
}
requireText(footer, 'support@partgraph.example', 'placeholder contact address')
requireText(footer, 'role="dialog"', 'footer information dialog semantics')
requireText(footer, 'aria-modal="true"', 'footer modal semantics')

requireText(settings, 'className="settings-accessibility-row"', 'compact accessibility row')
requireText(settings, 'aria-label="Text size"', 'compact text-size select')
if (settings.includes('settings-text-scale-grid')) {
  throw new Error('Accessibility must not regress to the oversized text-size card grid.')
}

console.log('Global product chrome, password guidance, compact accessibility, and footer contract passed.')
