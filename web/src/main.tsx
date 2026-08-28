import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import BlueprintShell from './blueprint/BlueprintShell'
import { installYearWheelInputSupport } from './year-wheel-input'
import './app.css'

installYearWheelInputSupport()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <BlueprintShell />
    </AuthGate>
  </StrictMode>,
)
