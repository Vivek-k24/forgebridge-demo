import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import OfflineBootstrap from './OfflineBootstrap'
import OfflineContinuity from './OfflineContinuity'
import PartGraphShell from './PartGraphShell'
import { registerPartGraphServiceWorker } from './service-worker'
import { initializeUiPreferences } from './ui-preferences'
import './app.css'
import './light-panel-contrast.css'
import './accessibility-ui.css'

initializeUiPreferences()
registerPartGraphServiceWorker()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <OfflineBootstrap>
      <AuthGate>
        <OfflineContinuity>
          <PartGraphShell />
        </OfflineContinuity>
      </AuthGate>
    </OfflineBootstrap>
  </StrictMode>,
)
