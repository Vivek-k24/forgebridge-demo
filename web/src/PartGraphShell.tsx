import { useEffect, useState } from 'react'
import { GarageWorkspace } from './GarageWorkspace'
import { GuidedRepairWorkspace } from './GuidedRepair'
import { RepairLogWorkspace } from './RepairLog'
import { RepairMemoryWorkspace } from './RepairMemory'
import { ResumeRepairWorkspace } from './ResumeRepair'
import { StartRepairWorkspace } from './StartRepair'
import './partgraph-shell.css'

type PageKey = 'garage' | 'start' | 'resume' | 'readiness' | 'guidance' | 'log'
type NavGroup = 'vehicle' | 'repair'

type NavItem = {
  key: PageKey
  label: string
  group: NavGroup
}

const NAV_ITEMS: NavItem[] = [
  { key: 'garage', label: 'Garage', group: 'vehicle' },
  { key: 'start', label: 'Start repair', group: 'repair' },
  { key: 'resume', label: 'Resume repair', group: 'repair' },
  { key: 'readiness', label: 'Readiness & inventory', group: 'repair' },
  { key: 'guidance', label: 'Guided repair', group: 'repair' },
  { key: 'log', label: 'Repair log', group: 'repair' },
]

const GROUP_LABELS: Record<NavGroup, string> = {
  vehicle: 'Vehicle',
  repair: 'Repair',
}

const PAGE_KEYS = new Set<PageKey>(NAV_ITEMS.map((item) => item.key))

function pageFromHash(): PageKey {
  const value = window.location.hash.replace(/^#\/?/, '') as PageKey
  return PAGE_KEYS.has(value) ? value : 'resume'
}

export default function PartGraphShell() {
  const [page, setPage] = useState<PageKey>(pageFromHash)
  const [preferredVehicleId, setPreferredVehicleId] = useState<string | null>(null)

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

  const navigation = (group: NavGroup) => (
    <>
      <p>{GROUP_LABELS[group]}</p>
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
      <GarageWorkspace
        initialMarket="US"
        onStartRepair={(vehicleId) => {
          setPreferredVehicleId(vehicleId)
          navigate('start')
        }}
      />
    )
  } else if (page === 'start') {
    content = (
      <StartRepairWorkspace
        preferredVehicleId={preferredVehicleId}
        onOpenGarage={() => navigate('garage')}
        onCreated={() => {
          setPreferredVehicleId(null)
          navigate('resume')
        }}
      />
    )
  } else if (page === 'readiness') {
    content = <RepairMemoryWorkspace />
  } else if (page === 'guidance') {
    content = <GuidedRepairWorkspace onOpenReadiness={() => navigate('readiness')} onStartRepair={() => navigate('start')} />
  } else if (page === 'log') {
    content = <RepairLogWorkspace />
  } else {
    content = (
      <ResumeRepairWorkspace
        onStartRepair={() => {
          setPreferredVehicleId(null)
          navigate('start')
        }}
        onOpenGarage={() => navigate('garage')}
        onOpenReadiness={() => navigate('readiness')}
        onOpenGuidance={() => navigate('guidance')}
        onOpenLog={() => navigate('log')}
      />
    )
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
          {navigation('vehicle')}
          {navigation('repair')}
        </nav>
        <div className="partgraph-runtime-note" aria-label="Production truth policy">
          <span><i aria-hidden="true" /> live workspace</span>
          <p>Verified guidance stays explicit. Private repair memory remains owner-scoped.</p>
        </div>
      </aside>
      <div className="partgraph-main">{content}</div>
    </div>
  )
}
