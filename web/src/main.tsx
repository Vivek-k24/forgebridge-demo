import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import OfflineContinuity from './OfflineContinuity'
import PartGraphShell from './PartGraphShell'
import { initializeUiPreferences } from './ui-preferences'
import './app.css'
import './light-panel-contrast.css'
import './accessibility-ui.css'

initializeUiPreferences()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <OfflineContinuity>
        <PartGraphShell />
      </OfflineContinuity>
    </AuthGate>
  </StrictMode>,
)
