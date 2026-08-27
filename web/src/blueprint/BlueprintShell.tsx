import { useCallback, useEffect, useMemo, useState } from 'react'
import App from '../App'
import { apiRequest, formatApiFailure } from '../api'
import { UserVehicleWorkspace } from '../UserVehicles'
import { BLUEPRINT_CONTRACTS, type BlueprintContract } from './contracts'
import './blueprint.css'

type PageKey =
  | 'resume'
  | 'garage'
  | 'repair'
  | 'assembly'
  | 'parts'
  | 'fasteners'
  | 'evidence'
  | 'inventory'
  | 'history'
  | 'system'

type VehicleIdentity = {
  year: number
  market: string
  make: string
  model: string
  generation: string | null
  trim: string | null
  body_style: string | null
  engine: string | null
  transmission: string | null
  drivetrain: string | null
}

type GarageVehicle = {
  id: string
  nickname: string | null
  canonical_configuration_id: string | null
  identity_source: 'manual' | 'vin'
  identity_resolution: 'matched' | 'ambiguous' | 'manual_candidate'
  identity: VehicleIdentity
  masked_vin: string | null
  archived_at: string | null
  updated_at: string
}

type NavItem = {
  key: PageKey
  label: string
  shortLabel: string
  group: 'work' | 'memory' | 'system'
}

const NAV_ITEMS: NavItem[] = [
  { key: 'resume', label: 'Resume', shortLabel: 'Resume', group: 'work' },
  { key: 'garage', label: 'Garage', shortLabel: 'Garage', group: 'work' },
  { key: 'repair', label: 'Repair session', shortLabel: 'Repair', group: 'work' },
  { key: 'assembly', label: 'Assembly', shortLabel: 'Assembly', group: 'work' },
  { key: 'parts', label: 'Parts', shortLabel: 'Parts', group: 'memory' },
  { key: 'fasteners', label: 'Fasteners', shortLabel: 'Fasteners', group: 'memory' },
  { key: 'evidence', label: 'Evidence', shortLabel: 'Evidence', group: 'memory' },
  { key: 'inventory', label: 'Inventory', shortLabel: 'Inventory', group: 'memory' },
  { key: 'history', label: 'History', shortLabel: 'History', group: 'memory' },
  { key: 'system', label: 'Blueprint map', shortLabel: 'Map', group: 'system' },
]

const PAGE_KEYS = new Set<PageKey>(NAV_ITEMS.map((item) => item.key))
const SELECTED_VEHICLE_KEY = 'partgraph-blueprint-selected-vehicle'

function pageFromHash(): PageKey {
  const candidate = window.location.hash.replace(/^#\/?/, '') as PageKey
  return PAGE_KEYS.has(candidate) ? candidate : 'resume'
}

function vehicleTitle(vehicle: GarageVehicle): string {
  if (vehicle.nickname) return vehicle.nickname
  return `${vehicle.identity.year} ${vehicle.identity.make} ${vehicle.identity.model}`
}

function vehicleSubtitle(vehicle: GarageVehicle): string {
  return [
    `${vehicle.identity.year} ${vehicle.identity.make} ${vehicle.identity.model}`,
    vehicle.identity.trim,
    vehicle.identity.engine,
    vehicle.identity.transmission,
  ]
    .filter(Boolean)
    .join(' · ')
}

function ContractState({ contract, compact = false }: { contract: BlueprintContract; compact?: boolean }) {
  return (
    <div className={compact ? 'contract-state contract-state--compact' : 'contract-state'}>
      <div className="contract-state__topline">
        <span className={`contract-dot contract-dot--${contract.status}`} aria-hidden="true" />
        <strong>{contract.label}</strong>
        <span className="contract-badge">{contract.status === 'bound' ? 'API bound' : 'API pending'}</span>
      </div>
      {!compact && <p>{contract.purpose}</p>}
      {!compact && (
        <code>{contract.path ?? 'Endpoint path intentionally unset until the backend contract exists.'}</code>
      )}
    </div>
  )
}

function PendingDataPanel({
  contract,
  title,
  children,
}: {
  contract: BlueprintContract
  title: string
  children?: React.ReactNode
}) {
  return (
    <section className="blue-card blue-card--contract">
      <div className="section-heading">
        <div>
          <p className="section-kicker">DATA BOUNDARY</p>
          <h2>{title}</h2>
        </div>
        <ContractState contract={contract} compact />
      </div>
      {children}
      {contract.status === 'pending' && (
        <div className="contract-empty">
          <strong>No fabricated records.</strong>
          <span>This surface becomes live when its backend endpoint is defined and connected.</span>
        </div>
      )}
    </section>
  )
}

function IdentityPills({ vehicle }: { vehicle: GarageVehicle }) {
  const values = [
    vehicle.identity.market,
    vehicle.identity.trim,
    vehicle.identity.body_style,
    vehicle.identity.engine,
    vehicle.identity.transmission,
    vehicle.identity.drivetrain,
  ].filter(Boolean)

  return (
    <div className="identity-pills">
      {values.map((value) => (
        <span key={value}>{value}</span>
      ))}
    </div>
  )
}

function EmptyVehicle({ onGarage }: { onGarage: () => void }) {
  return (
    <div className="empty-state empty-state--large">
      <p className="section-kicker">GARAGE REQUIRED</p>
      <h2>Add a vehicle before starting a repair.</h2>
      <p>Vehicle identity anchors every later assembly, part, fastener, evidence, and repair-session record.</p>
      <button className="primary-action" type="button" onClick={onGarage}>
        Open garage
      </button>
    </div>
  )
}

function ResumeScreen({
  vehicle,
  onNavigate,
}: {
  vehicle: GarageVehicle | null
  onNavigate: (page: PageKey) => void
}) {
  return (
    <div className="screen-stack">
      <section className="blue-hero blue-hero--resume">
        <div>
          <p className="section-kicker">PARTGRAPH · RESUME</p>
          <h1>Return to the exact physical state of the repair.</h1>
          <p>
            The home screen is intentionally centered on repair continuity: current vehicle, current session,
            next verified action, changed parts, fasteners, and blockers.
          </p>
        </div>
        <div className="hero-loop" aria-label="PartGraph repair loop">
          <span>Understand</span>
          <span>Plan</span>
          <span>Act</span>
          <span>Observe</span>
          <span>Remember</span>
          <span>Adapt</span>
          <span>Continue</span>
        </div>
      </section>

      {!vehicle ? (
        <EmptyVehicle onGarage={() => onNavigate('garage')} />
      ) : (
        <>
          <section className="blue-card vehicle-context-card">
            <div>
              <p className="section-kicker">CURRENT VEHICLE</p>
              <h2>{vehicleTitle(vehicle)}</h2>
              <p>{vehicleSubtitle(vehicle)}</p>
              <IdentityPills vehicle={vehicle} />
            </div>
            <button className="secondary-action" type="button" onClick={() => onNavigate('garage')}>
              Change vehicle
            </button>
          </section>

          <PendingDataPanel contract={BLUEPRINT_CONTRACTS.activeRepairSession} title="Active repair session">
            <div className="resume-grid">
              <div className="resume-focus">
                <p className="field-label">Next safe action</p>
                <div className="data-slot">Waiting for repair-session state</div>
              </div>
              <div>
                <p className="field-label">Current step</p>
                <div className="data-slot data-slot--small">Waiting for repair plan</div>
              </div>
              <div>
                <p className="field-label">Blockers</p>
                <div className="data-slot data-slot--small">Waiting for dependency state</div>
              </div>
              <div>
                <p className="field-label">Last observation</p>
                <div className="data-slot data-slot--small">Waiting for session events</div>
              </div>
            </div>
            <button className="primary-action" type="button" onClick={() => onNavigate('repair')}>
              Open repair workspace
            </button>
          </PendingDataPanel>
        </>
      )}
    </div>
  )
}

function GarageScreen() {
  const [mode, setMode] = useState<'private' | 'identity'>('private')

  return (
    <div className="screen-stack">
      <section className="page-intro">
        <p className="section-kicker">GARAGE</p>
        <h1>Identify the physical vehicle without turning observations into shared truth.</h1>
        <p>
          Saved vehicles are private owner records. VIN and manual details can help resolve identity, but canonical
          vehicle knowledge remains a separate trust boundary.
        </p>
      </section>

      <div className="segmented-control" role="tablist" aria-label="Garage mode">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'private'}
          className={mode === 'private' ? 'is-active' : ''}
          onClick={() => setMode('private')}
        >
          My vehicles & VIN
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'identity'}
          className={mode === 'identity' ? 'is-active' : ''}
          onClick={() => setMode('identity')}
        >
          Vehicle details
        </button>
      </div>

      {mode === 'private' ? (
        <section className="blue-card blueprint-embedded-workspace">
          <UserVehicleWorkspace initialMarket="US" onUseDetails={() => setMode('identity')} />
        </section>
      ) : (
        <section className="blue-card blueprint-embedded-workspace blueprint-embedded-workspace--details">
          <App />
        </section>
      )}
    </div>
  )
}

function RepairScreen({ vehicle }: { vehicle: GarageVehicle | null }) {
  if (!vehicle) return <EmptyVehicle onGarage={() => (window.location.hash = '#/garage')} />

  return (
    <div className="screen-stack">
      <section className="page-intro page-intro--with-context">
        <div>
          <p className="section-kicker">REPAIR SESSION</p>
          <h1>One stateful workspace for the job from first removal to final inspection.</h1>
          <p>{vehicleSubtitle(vehicle)}</p>
        </div>
        <span className="context-chip">{vehicleTitle(vehicle)}</span>
      </section>

      <PendingDataPanel contract={BLUEPRINT_CONTRACTS.repairPlan} title="Verified plan and next action">
        <div className="repair-layout">
          <div className="repair-timeline">
            <div className="workspace-column-heading">Repair steps</div>
            <div className="data-slot data-slot--tall">Step dependency graph will render here</div>
          </div>
          <div className="repair-action-panel">
            <div className="workspace-column-heading">Current action</div>
            <div className="data-slot data-slot--tall">Verified action, prerequisites, warnings, and completion controls</div>
          </div>
        </div>
      </PendingDataPanel>

      <div className="two-column-grid">
        <PendingDataPanel contract={BLUEPRINT_CONTRACTS.fastenerState} title="Fasteners in this step" />
        <PendingDataPanel contract={BLUEPRINT_CONTRACTS.inventory} title="Parts readiness" />
      </div>
    </div>
  )
}

function AssemblyScreen({ vehicle }: { vehicle: GarageVehicle | null }) {
  return (
    <div className="screen-stack">
      <section className="page-intro">
        <p className="section-kicker">ASSEMBLY</p>
        <h1>Canonical assembly on one side. Actual observed vehicle state on the other.</h1>
        <p>{vehicle ? vehicleSubtitle(vehicle) : 'Select a vehicle from the garage to anchor assembly state.'}</p>
      </section>
      <PendingDataPanel contract={BLUEPRINT_CONTRACTS.assemblyState} title="Assembly state">
        <div className="assembly-toolbar">
          <input aria-label="Search assembly" placeholder="Search assembly" disabled />
          <div className="filter-row" aria-label="Assembly state filters">
            <button type="button" disabled>All</button>
            <button type="button" disabled>Installed</button>
            <button type="button" disabled>Removed</button>
            <button type="button" disabled>Changed</button>
          </div>
        </div>
        <div className="assembly-layout">
          <div className="data-slot data-slot--tall">Assembly hierarchy</div>
          <div className="data-slot data-slot--tall">Selected node state and evidence</div>
        </div>
      </PendingDataPanel>
    </div>
  )
}

function PartsScreen({ vehicle }: { vehicle: GarageVehicle | null }) {
  const [query, setQuery] = useState('')
  return (
    <div className="screen-stack">
      <section className="page-intro">
        <p className="section-kicker">PARTS</p>
        <h1>Repair-relevant parts with provenance, fitment, condition, and current state.</h1>
        <p>{vehicle ? vehicleSubtitle(vehicle) : 'No vehicle selected.'}</p>
      </section>
      <PendingDataPanel contract={BLUEPRINT_CONTRACTS.partsState} title="Parts workspace">
        <div className="search-strip">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search part name or known identifier"
            aria-label="Search parts"
          />
          <button type="button" disabled={BLUEPRINT_CONTRACTS.partsState.status === 'pending'}>
            Search
          </button>
        </div>
        {query && BLUEPRINT_CONTRACTS.partsState.status === 'pending' && (
          <p className="input-note">Search text stays local; no request is sent until the parts contract is bound.</p>
        )}
        <div className="data-slot data-slot--tall">Part results and evidence will come only from backend data</div>
      </PendingDataPanel>
    </div>
  )
}

function FastenersScreen() {
  return (
    <div className="screen-stack">
      <section className="page-intro">
        <p className="section-kicker">FASTENER MEMORY</p>
        <h1>Know what came out, where it was stored, and exactly where it goes back.</h1>
      </section>
      <PendingDataPanel contract={BLUEPRINT_CONTRACTS.fastenerState} title="Fastener and small-part memory">
        <div className="two-column-grid">
          <div className="data-slot data-slot--tall">Storage locations from the repair session</div>
          <div className="data-slot data-slot--tall">Removed and installed fasteners from session state</div>
        </div>
      </PendingDataPanel>
    </div>
  )
}

function EvidenceScreen() {
  return (
    <div className="screen-stack">
      <section className="page-intro">
        <p className="section-kicker">EVIDENCE</p>
        <h1>Photos and observations describe the real vehicle without silently changing mechanical truth.</h1>
      </section>
      <PendingDataPanel contract={BLUEPRINT_CONTRACTS.evidence} title="Evidence and observations">
        <div className="evidence-capture">
          <div className="data-slot data-slot--tall">Photo and observation timeline</div>
          <div className="capture-panel">
            <p className="field-label">Add observation</p>
            <button type="button" disabled>Take or upload photo</button>
            <button type="button" disabled>Record structured observation</button>
            <p>Capture controls stay disabled until authenticated upload and observation contracts exist.</p>
          </div>
        </div>
      </PendingDataPanel>
    </div>
  )
}

function InventoryScreen() {
  return (
    <div className="screen-stack">
      <section className="page-intro">
        <p className="section-kicker">INVENTORY</p>
        <h1>Separate physical condition from procurement readiness.</h1>
        <p>Required, available, ordered, missing, installed, and damaged are different facts and should not collapse into one status.</p>
      </section>
      <PendingDataPanel contract={BLUEPRINT_CONTRACTS.inventory} title="Parts readiness and procurement">
        <div className="status-rail">
          <span>Required</span>
          <span>Available</span>
          <span>Ordered</span>
          <span>Missing</span>
          <span>Installed</span>
        </div>
        <div className="data-slot data-slot--tall">Inventory records from the repair session</div>
      </PendingDataPanel>
    </div>
  )
}

function HistoryScreen() {
  return (
    <div className="screen-stack">
      <section className="page-intro">
        <p className="section-kicker">HISTORY & RESUME</p>
        <h1>The repair should be reconstructable from durable events, not memory or chat history.</h1>
      </section>
      <PendingDataPanel contract={BLUEPRINT_CONTRACTS.sessionHistory} title="Session events and checkpoints">
        <div className="history-layout">
          <div className="data-slot data-slot--tall">Append-only event timeline</div>
          <div className="data-slot data-slot--tall">Resume checkpoint and reorientation summary</div>
        </div>
      </PendingDataPanel>
    </div>
  )
}

function SystemMapScreen() {
  const contracts = Object.values(BLUEPRINT_CONTRACTS)
  const bound = contracts.filter((contract) => contract.status === 'bound').length

  return (
    <div className="screen-stack">
      <section className="page-intro">
        <p className="section-kicker">BLUEPRINT MAP</p>
        <h1>UI surfaces and their backend ownership stay visible as the product grows.</h1>
        <p>{bound} contracts are currently bound to real API paths. Pending contracts deliberately have no invented URL.</p>
      </section>
      <section className="blue-card">
        <div className="contract-map">
          {contracts.map((contract) => (
            <ContractState key={contract.id} contract={contract} />
          ))}
        </div>
      </section>
    </div>
  )
}

export default function BlueprintShell() {
  const [page, setPage] = useState<PageKey>(pageFromHash)
  const [vehicles, setVehicles] = useState<GarageVehicle[]>([])
  const [garageLoading, setGarageLoading] = useState(true)
  const [garageError, setGarageError] = useState<string | null>(null)
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(() =>
    window.localStorage.getItem(SELECTED_VEHICLE_KEY),
  )

  const loadVehicles = useCallback(async () => {
    setGarageLoading(true)
    setGarageError(null)
    try {
      const items = await apiRequest<GarageVehicle[]>('/api/v1/user-vehicles?limit=100')
      setVehicles(items.filter((vehicle) => vehicle.archived_at === null))
    } catch (error) {
      setGarageError(formatApiFailure(error, 'Could not load your garage.'))
    } finally {
      setGarageLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadVehicles()
  }, [loadVehicles])

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    if (vehicles.length === 0) {
      setSelectedVehicleId(null)
      window.localStorage.removeItem(SELECTED_VEHICLE_KEY)
      return
    }
    if (!selectedVehicleId || !vehicles.some((vehicle) => vehicle.id === selectedVehicleId)) {
      const next = vehicles[0].id
      setSelectedVehicleId(next)
      window.localStorage.setItem(SELECTED_VEHICLE_KEY, next)
    }
  }, [selectedVehicleId, vehicles])

  const selectedVehicle = useMemo(
    () => vehicles.find((vehicle) => vehicle.id === selectedVehicleId) ?? null,
    [selectedVehicleId, vehicles],
  )

  const navigate = useCallback((next: PageKey) => {
    window.location.hash = `#/${next}`
    setPage(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const selectVehicle = (vehicleId: string) => {
    setSelectedVehicleId(vehicleId)
    window.localStorage.setItem(SELECTED_VEHICLE_KEY, vehicleId)
  }

  let screen: React.ReactNode
  switch (page) {
    case 'garage':
      screen = <GarageScreen />
      break
    case 'repair':
      screen = <RepairScreen vehicle={selectedVehicle} />
      break
    case 'assembly':
      screen = <AssemblyScreen vehicle={selectedVehicle} />
      break
    case 'parts':
      screen = <PartsScreen vehicle={selectedVehicle} />
      break
    case 'fasteners':
      screen = <FastenersScreen />
      break
    case 'evidence':
      screen = <EvidenceScreen />
      break
    case 'inventory':
      screen = <InventoryScreen />
      break
    case 'history':
      screen = <HistoryScreen />
      break
    case 'system':
      screen = <SystemMapScreen />
      break
    case 'resume':
    default:
      screen = <ResumeScreen vehicle={selectedVehicle} onNavigate={navigate} />
      break
  }

  return (
    <div className="blueprint-app">
      <aside className="blueprint-sidebar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">PG</div>
          <div>
            <strong>PartGraph</strong>
            <span>Repair continuity</span>
          </div>
        </div>

        <div className="blueprint-label">UI BLUEPRINT</div>

        <nav className="desktop-nav" aria-label="PartGraph blueprint">
          <p>Repair</p>
          {NAV_ITEMS.filter((item) => item.group === 'work').map((item) => (
            <button
              key={item.key}
              type="button"
              className={page === item.key ? 'is-active' : ''}
              onClick={() => navigate(item.key)}
            >
              {item.label}
            </button>
          ))}
          <p>Memory</p>
          {NAV_ITEMS.filter((item) => item.group === 'memory').map((item) => (
            <button
              key={item.key}
              type="button"
              className={page === item.key ? 'is-active' : ''}
              onClick={() => navigate(item.key)}
            >
              {item.label}
            </button>
          ))}
          <p>Architecture</p>
          {NAV_ITEMS.filter((item) => item.group === 'system').map((item) => (
            <button
              key={item.key}
              type="button"
              className={page === item.key ? 'is-active' : ''}
              onClick={() => navigate(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <div className="blueprint-main">
        <header className="blueprint-topbar">
          <div className="vehicle-switcher">
            <span>Vehicle</span>
            {garageLoading ? (
              <div className="vehicle-loading">Loading garage…</div>
            ) : vehicles.length > 0 ? (
              <select
                value={selectedVehicleId ?? ''}
                onChange={(event) => selectVehicle(event.target.value)}
                aria-label="Current vehicle"
              >
                {vehicles.map((vehicle) => (
                  <option key={vehicle.id} value={vehicle.id}>
                    {vehicleTitle(vehicle)}
                  </option>
                ))}
              </select>
            ) : (
              <button type="button" onClick={() => navigate('garage')}>
                Add vehicle
              </button>
            )}
          </div>
          <div className="topbar-status">
            <span className="live-dot" aria-hidden="true" />
            Backend-sourced only
          </div>
        </header>

        {garageError && (
          <div className="global-data-error" role="alert">
            <span>{garageError}</span>
            <button type="button" onClick={() => void loadVehicles()}>Retry</button>
          </div>
        )}

        <main className="blueprint-content">{screen}</main>
      </div>

      <nav className="mobile-nav" aria-label="PartGraph mobile blueprint">
        {NAV_ITEMS.filter((item) => ['resume', 'garage', 'repair', 'parts', 'history'].includes(item.key)).map((item) => (
          <button
            key={item.key}
            type="button"
            className={page === item.key ? 'is-active' : ''}
            onClick={() => navigate(item.key)}
          >
            {item.shortLabel}
          </button>
        ))}
      </nav>
    </div>
  )
}
