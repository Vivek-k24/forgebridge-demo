import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import PartGraphShell from './PartGraphShell'
import ProductionLaunch from './ProductionLaunch'
import { installYearWheelInputSupport } from './year-wheel-input'
import './app.css'

installYearWheelInputSupport()

const app = <PartGraphShell />
const directPagesPreview = import.meta.env.MODE === 'pages'
  && window.location.hostname.endsWith('github.io')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {directPagesPreview ? (
      <ProductionLaunch />
    ) : (
      <AuthGate>{app}</AuthGate>
    )}
  </StrictMode>,
)
