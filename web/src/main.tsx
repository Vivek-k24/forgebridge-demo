import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import PartGraphShell from './PartGraphShell'
import { installYearWheelInputSupport } from './year-wheel-input'
import './app.css'

installYearWheelInputSupport()

const staticPreview = import.meta.env.VITE_PARTGRAPH_STATIC_PREVIEW === 'true'
const app = <PartGraphShell />

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {staticPreview ? (
      <div className="partgraph-pages-preview">
        <div className="partgraph-pages-preview-strip" role="status">
          STATIC MAIN PREVIEW · FASTAPI / POSTGRESQL NOT HOSTED ON GITHUB PAGES
        </div>
        {app}
      </div>
    ) : (
      <AuthGate>{app}</AuthGate>
    )}
  </StrictMode>,
)
