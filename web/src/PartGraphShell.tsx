import { useEffect, useState } from 'react'
import { AccountSettingsWorkspace } from './AccountSettings'
import { AdminWorkspace } from './AdminWorkspace'
import { apiRequest } from './api'
import { GarageRepairContext } from './GarageRepairContext'
import { GarageWorkspace } from './GarageWorkspace'
import { GuidedRepairWorkspace } from './GuidedRepair'
import { HomeWorkspace } from './HomeWorkspace'
import { RepairCompletionWorkspace } from './RepairCompletion'
import { RepairLogWorkspace } from './RepairLog'
import { RepairMemoryWorkspace } from './RepairMemory'
import { ResumeRepairWorkspace } from './ResumeRepair'
import { StartRepairWorkspace } from './StartRepair'
import './partgraph-shell.css'

type PageKey = 'home' | 'settings' | 'admin' | 'garage' | 'start' | 'resume' | 'readiness' | 'guidance' | 'completion' | 'log'
type UserRole = 'owner' | 'contributor' | 'reviewer' | 'curator' | 'operator_admin'
type NavItem = { key: PageKey; label: string }
type AuthResult = { user: { role: UserRole } }
type PreviewOperatorBootstrapStatus = { available: boolean }

const PRIMARY_NAV_ITEMS: NavItem[] = [
  { key: 'garage', label: 'Garage' },
  { key: 'readiness', label: 'Inventory' },
  { key: 'log', label: 'Repair log' },
]

const UTILITY_NAV_ITEMS: NavItem[] = [
  { key: 'settings', label: 'Settings' },
]

const REPAIR_WORKSPACE_ITEMS: NavItem[] = [
  { key: 'resume', label: 'Overview' },
  { key: 'guidance', label: 'Guided repair' },
  { key: 'log', label: 'Repair log' },
]

const REPAIR_WORKSPACE_KEYS = new Set<PageKey>(REPAIR_WORKSPACE_ITEMS.map((item) => item.key))
const PAGE_KEYS = new Set<PageKey>([
  'home',
  'settings',
  'admin',
  'garage',
  'start',
  'resume',
  'readiness',
  'guidance',
  'completion',
  'log',
])

function pageFromHash(): PageKey {
  const value = window.location.hash.replace(/^#\/?/, '') as PageKey
  return PAGE_KEYS.has(value) ? value : 'home'
}

export default function PartGraphShell() {
  const [page, setPage] = useState<PageKey>(pageFromHash)
  const [preferredVehicleId, setPreferredVehicleId] = useState<string | null>(null)
  const [isOperatorAdmin, setIsOperatorAdmin] = useState(false)
  const [isAdminSetupAvailable, setIsAdminSetupAvailable] = useState(false)

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    let active = true
    async function loadAdminState() {
      try {
        const result = await apiRequest<AuthResult>('/api/v1/auth/me')
        if (!active) return
        const operator = result.user.role === 'operator_admin'
        setIsOperatorAdmin(operator)
        if (operator) {
          setIsAdminSetupAvailable(false)
          return
        }
        try {
          const bootstrap = await apiRequest<PreviewOperatorBootstrapStatus>('/api/v1/operator/preview-bootstrap/status')
          if (active) setIsAdminSetupAvailable(bootstrap.available)
        } catch {
          if (active) setIsAdminSetupAvailable(false)
        }
      } catch {
        if (!active) return
        setIsOperatorAdmin(false)
        setIsAdminSetupAvailable(false)
      }
    }
    void loadAdminState()
    return () => { active = false }
  }, [])

  function navigate(next: PageKey) {
    setPage(next)
    window.location.hash = `#/${next}`
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function navButton(item: NavItem) {
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
  }

  let content: React.ReactNode
  if (page === 'home') {
    content = <HomeWorkspace onOpenGarage={() => navigate('garage')} onStartRepair={() => { setPreferredVehicleId(null); navigate('start') }} onResumeRepair={() => navigate('resume')} />
  } else if (page === 'settings') {
    content = <AccountSettingsWorkspace />
  } else if (page === 'admin') {
    content = <AdminWorkspace />
  } else if (page === 'garage') {
    content = (
      <>
        <GarageRepairContext />
        <GarageWorkspace initialMarket="US" onStartRepair={(vehicleId) => { setPreferredVehicleId(vehicleId); navigate('start') }} />
      </>
    )
  } else if (page === 'start') {
    content = <StartRepairWorkspace preferredVehicleId={preferredVehicleId ?? ''} onOpenGarage={() => navigate('garage')} onCreated={() => { setPreferredVehicleId(null); navigate('resume') }} />
  } else if (page === 'readiness') {
    content = <RepairMemoryWorkspace />
  } else if (page === 'guidance') {
    content = <GuidedRepairWorkspace onOpenReadiness={() => navigate('readiness')} onStartRepair={() => navigate('start')} />
  } else if (page === 'completion') {
    content = <RepairCompletionWorkspace />
  } else if (page === 'log') {
    content = <RepairLogWorkspace />
  } else {
    content = (
      <ResumeRepairWorkspace
        onStartRepair={() => { setPreferredVehicleId(null); navigate('start') }}
        onOpenGarage={() => navigate('garage')}
        onOpenReadiness={() => navigate('readiness')}
        onOpenGuidance={() => navigate('guidance')}
        onOpenCompletion={() => navigate('completion')}
        onOpenLog={() => navigate('log')}
      />
    )
  }

  return (
    <div className="partgraph-app-shell">
      <aside className="partgraph-sidebar" aria-label="PartGraph workspace navigation">
        <button type="button" className="partgraph-brand" aria-label="PartGraph home" onClick={() => navigate('home')}>
          <div className="partgraph-brand-mark" aria-hidden="true">PG</div>
          <div><strong>PartGraph</strong><span>Repair continuity</span></div>
        </button>
        <nav className="partgraph-nav">
          <div className="partgraph-nav-primary">{PRIMARY_NAV_ITEMS.map(navButton)}</div>
          <div className="partgraph-nav-utility">
            {UTILITY_NAV_ITEMS.map(navButton)}
            {(isOperatorAdmin || isAdminSetupAvailable) && (
              <button
                type="button"
                className={page === 'admin' ? 'partgraph-nav-item partgraph-nav-item--active' : 'partgraph-nav-item'}
                aria-current={page === 'admin' ? 'page' : undefined}
                onClick={() => navigate('admin')}
              >
                <span>{isOperatorAdmin ? 'Admin' : 'Admin setup'}</span>
              </button>
            )}
          </div>
        </nav>
        <div className="partgraph-runtime-note" aria-label="Production truth policy"><span><i aria-hidden="true" /> live workspace</span><p>Verified guidance stays explicit. Private repair memory remains owner-scoped.</p></div>
      </aside>
      <div className="partgraph-main">
        {REPAIR_WORKSPACE_KEYS.has(page) && (
          <nav className="partgraph-repair-nav" aria-label="Current repair workspace">
            <span>Current repair</span>
            <div>{REPAIR_WORKSPACE_ITEMS.map((item) => <button key={item.key} type="button" className={item.key === page ? 'partgraph-repair-nav__item partgraph-repair-nav__item--active' : 'partgraph-repair-nav__item'} aria-current={item.key === page ? 'page' : undefined} onClick={() => navigate(item.key)}>{item.label}</button>)}</div>
          </nav>
        )}
        {content}
      </div>
    </div>
  )
}
