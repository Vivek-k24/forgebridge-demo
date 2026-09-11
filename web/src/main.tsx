import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import PartGraphShell from './PartGraphShell'
import './app.css'
import './light-panel-contrast.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <PartGraphShell />
    </AuthGate>
  </StrictMode>,
)
