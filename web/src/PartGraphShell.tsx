import { useEffect, useState } from 'react'
import App from './App'
import { RepairMemoryWorkspace } from './RepairMemory'
import { RepairSessionWorkspace } from './RepairSessions'
import { UserVehicleWorkspace } from './UserVehicles'
import './partgraph-shell.css'

type PageKey = 'resume' | 'garage' | 'details' | 'repair' | 'inventory'

type NavItem = {
  key: PageKey
  label: string
  group: 'repair' | 'readiness'
}

const NAV_ITEMS: NavItem[] = [
  { key: 'resume', label: 'Resume', group: 'repair' },
  { key: 'garage', label: 'Garage & VIN', group: 'repair' },
  { key: 'details', label: 'Vehicle details', group: 'repair' },
  { key: 'repair', label: 'Repair session', group: 'repair' },
  { key: 'inventory', label: 'Inventory', group: 'readiness' },
]

const PAGE_KEYS = new Set<PageKey>([
  'resume',
  'garage',
  'details',
  'repair',
  'inventory',
])

function pageFromHash(): PageKey {
  const value = window.location.hash.replace(/^#\/?/, '') as PageKey
  return PAGE_KEYS.has(value) ? value : 'resume'
}

export default function PartGraphShell() {
  const [page, setPage] = useState<PageKey>(pageFromHash)

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function navigate(next: PageKey) {
    setPage(next)
    window.location.hash = `#/${next}`
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const navigation = (group: NavItem['group']) => (
    <>
      <p>{group === 'repair' ? 'Repair' : 'Readiness'}</p>
      {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
        const active = item.key === page
        return (
          <button
            key={item.key}
            type="button"
            className={active ? 'partgraph-nav-item partgraph-nav-item--active' : 'partgraph-nav-item'}
            aria-current={active ? 'page' : undefined}
            onClick={() => navigate(item.key)}
          >
            <span>{item.label}</span>
          </button>
        )
      })}
    </>
  )

  let content: React.ReactNode
  if (page === 'garage') {
    content = (
      <main className="shell partgraph-page-shell">
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
            onUseDetails={() => navigate('details')}
          />
        </section>
      </main>
    )
  } else if (page === 'details') {
    content = (
      <div className="partgraph-details-host">
        <App />
      </div>
    )
  } else if (page === 'inventory') {
    content = <RepairMemoryWorkspace />
  } else {
    content = <RepairSessionWorkspace onOpenGarage={() => navigate('garage')} />
  }

  return (
    <div className="partgraph-app-shell">
      <aside className="partgraph-sidebar" aria-label="PartGraph workspace navigation">
        <div className="partgraph-brand">
          <div className="partgraph-brand-mark" aria-hidden="true">PG</div>
          <div>
            <strong>PartGraph</strong>
            <span>Repair continuity</span>
          </div>
        </div>
        <nav className="partgraph-nav">
          {navigation('repair')}
          {navigation('readiness')}
        </nav>
      </aside>
      <div className="partgraph-main">{content}</div>
    </div>
  )
}
