import { useState } from 'react'
import App from './App'
import { UserVehicleWorkspace } from './UserVehicles'

export default function Block5Shell() {
  const [mode, setMode] = useState<'details' | 'vin'>('details')

  return (
    <>
      <div className="block5-mode-shell">
        <nav className="block5-mode-tabs" aria-label="Vehicle identification method">
          <button
            type="button"
            aria-pressed={mode === 'details'}
            className={mode === 'details' ? 'block5-mode-tab block5-mode-tab--active' : 'block5-mode-tab'}
            onClick={() => setMode('details')}
          >
            Vehicle details
          </button>
          <button
            type="button"
            aria-pressed={mode === 'vin'}
            className={mode === 'vin' ? 'block5-mode-tab block5-mode-tab--active' : 'block5-mode-tab'}
            onClick={() => setMode('vin')}
          >
            VIN & my vehicles
          </button>
        </nav>
      </div>

      {mode === 'details' ? (
        <div className="block5-details-host">
          <App />
        </div>
      ) : (
        <main className="shell">
          <header className="hero">
            <p className="eyebrow">PARTGRAPH · PRIVATE GARAGE</p>
            <h1>Identify and remember your vehicle.</h1>
            <p className="lede">
              VIN evidence helps identify the car, while PartGraph keeps the private vehicle record
              separate from shared canonical mechanical truth.
            </p>
          </header>
          <section className="workspace panel">
            <UserVehicleWorkspace
              initialMarket="US"
              onUseDetails={() => setMode('details')}
            />
          </section>
        </main>
      )}
    </>
  )
}
