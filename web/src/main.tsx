import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import Block5Shell from './Block5Shell'
import { installYearWheelInputSupport } from './year-wheel-input'
import './app.css'

installYearWheelInputSupport()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <Block5Shell />
    </AuthGate>
  </StrictMode>,
)
