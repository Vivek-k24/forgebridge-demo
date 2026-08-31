import './production-launch.css'

const LIVE_APP_URL = 'https://partgraph-main.vercel.app/#/resume'

const CAPABILITIES = [
  {
    title: 'Identify and save your vehicle',
    detail: 'Use verified configuration lookup or private VIN/manual identity without promoting guesses into shared truth.',
  },
  {
    title: 'Keep a private garage',
    detail: 'Your saved vehicles and VIN-derived identity stay in the authenticated owner workspace.',
  },
  {
    title: 'Pause and resume repairs',
    detail: 'RepairSession history, device lease state, observations, photos, and physical repair memory survive interruptions.',
  },
  {
    title: 'Track readiness without invented data',
    detail: 'Inventory and verified guidance fail closed when a licensed, applicable repair definition is not available yet.',
  },
]

export default function ProductionLaunch() {
  return (
    <main className="launch-shell">
      <section className="launch-card">
        <div className="launch-brand-row">
          <div className="launch-mark" aria-hidden="true">PG</div>
          <div>
            <p className="launch-kicker">PARTGRAPH · LIVE WORKSPACE</p>
            <span className="launch-status"><i aria-hidden="true" /> Production API + PostgreSQL connected</span>
          </div>
        </div>

        <div className="launch-hero">
          <p className="launch-overline">GitHub Pages is now the static preview and asset delivery surface.</p>
          <h1>Run the real PartGraph workspace on Vercel.</h1>
          <p>
            The live app uses the production FastAPI service and Neon PostgreSQL database on the same
            browser origin, so secure login, private garage state, repair sessions, inventory, and
            resume behavior work together instead of falling back to a static demo.
          </p>
          <div className="launch-actions">
            <a className="launch-primary" href={LIVE_APP_URL}>Open live PartGraph</a>
            <a className="launch-secondary" href="https://github.com/Vivek-k24/forgebridge-demo">View source</a>
          </div>
        </div>

        <div className="launch-capabilities" aria-label="Available PartGraph capabilities">
          {CAPABILITIES.map((item, index) => (
            <article key={item.title}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <div>
                <h2>{item.title}</h2>
                <p>{item.detail}</p>
              </div>
            </article>
          ))}
        </div>

        <div className="launch-boundary">
          <strong>Repair procedures remain intentionally fail-closed.</strong>
          <p>
            PartGraph currently has a real verified 2009 Honda Civic Hybrid identity in production,
            but it will not display a repair procedure until an approved source and exact vehicle
            applicability are available.
          </p>
        </div>
      </section>
    </main>
  )
}
