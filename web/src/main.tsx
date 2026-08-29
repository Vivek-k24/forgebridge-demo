import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import PartGraphShell from './PartGraphShell'
import { installYearWheelInputSupport } from './year-wheel-input'
import './app.css'

installYearWheelInputSupport()

const app = <PartGraphShell />
const pagesPreview = import.meta.env.MODE === 'pages'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {pagesPreview ? (
      <div className="authenticated-shell">
        <div className="account-strip">
          <div>
            <span className="account-dot" aria-hidden="true" />
            <span className="account-status">STATIC MAIN PREVIEW</span>
            <span className="account-email">GitHub Pages · backend actions unavailable</span>
          </div>
        </div>
        {app}
      </div>
    ) : (
      <AuthGate>{app}</AuthGate>
    )}
  </StrictMode>,
)
