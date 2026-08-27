import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthGate from './AuthGate'
import Block5Shell from './Block5Shell'
import './app.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <Block5Shell />
    </AuthGate>
  </StrictMode>,
)
