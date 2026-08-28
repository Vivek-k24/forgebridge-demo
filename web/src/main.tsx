import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import PartGraphShell from './PartGraphShell'
import { installYearWheelInputSupport } from './year-wheel-input'
import './app.css'

installYearWheelInputSupport()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <PartGraphShell />
    </AuthGate>
  </StrictMode>,
)
