import { useEffect, useState } from 'react'
import App from './App'
import { RepairMemoryWorkspace } from './RepairMemory'
import { RepairSessionWorkspace } from './RepairSessions'
import { UserVehicleWorkspace } from './UserVehicles'
import './partgraph-shell.css'

type MemoryPageKey = 'fasteners' | 'evidence' | 'inventory'
type PageKey = 'resume' | 'garage' | 'details' | 'repair' | MemoryPageKey

type NavItem = {
  key: string
  label: string
  group: 'repair' | 'memory'
  page?: PageKey
  pending?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { key: 'resume', label: 'Resume', group: 'repair', page: 'resume' },
  { key: 'garage', label: 'Garage & VIN', group: 'repair', page: 'garage' },
  { key: 'details', label: 'Vehicle details', group: 'repair', page: 'details' },
  { key: 'repair', label: 'Repair session', group: 'repair', page: 'repair' },
  { key: 'assembly', label: 'Assembly', group: 'memory', pending: true },
  { key: 'parts', label: 'Parts', group: 'memory', pending: true },
  { key: 'fasteners', label: 'Fasteners', group: 'memory', page: 'fasteners' },
  { key: 'evidence', label: 'Evidence', group: 'memory', page: 'evidence' },
  { key: 'inventory', label: 'Inventory', group: 'memory', page: 'inventory' },
  { key: 'history', label: 'History', group: 'memory', pending: true },
]

const PAGE_KEYS = new Set<PageKey>([
  'resume',
  'garage',
  'details',
  'repair',
  'fasteners',
  'evidence',
  'inventory',
])

function pageFromHash(): PageKey {
  const value = window.location.hash.replace(/^#\/?/, '') as PageKey
  return PAGE_KEYS.has(value) ? value : 'resume'
}

function isMemoryPage(page: PageKey): page is MemoryPageKey {
  return page === 'fasteners' || page === 'evidence' || page === 'inventory'
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
      <p>{group === 'repair' ? 'Repair' : 'Memory'}</p>
      {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
        const active = item.page === page
        if (item.pending || !item.page) {
          return (
            <button
              key={item.key}
              type="button"
              className="partgraph-nav-item partgraph-nav-item--pending"
              disabled
              title="Backend contract not implemented yet"
            >
              <span>{item.label}</span>
              <small>pending</small>
            </button>
          )
        }
        return (
          <button
            key={item.key}
            type="button"
            className={active ? 'partgraph-nav-item partgraph-nav-item--active' : 'partgraph-nav-item'}
            aria-current={active ? 'page' : undefined}
            onClick={() => navigate(item.page!)}
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
  } else if (isMemoryPage(page)) {
    content = <RepairMemoryWorkspace initialView={page} />
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
          {navigation('memory')}
        </nav>
      </aside>
      <div className="partgraph-main">{content}</div>
    </div>
  )
}
