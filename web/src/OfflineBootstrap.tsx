import { useEffect, useState, type ReactNode } from 'react'
import { activeRepairSessionId } from './active-repair'
import { AUTH_STATE_CLEARED_EVENT } from './api'
import { OfflineRepairWorkspace } from './OfflineRepair'
import { loadCachedOfflineRepairPack, type OfflineRepairPack } from './offline-repair'
import './offline-continuity.css'

const SECTIONS = ['resume', 'readiness', 'guidance', 'completion', 'log'] as const
type Section = (typeof SECTIONS)[number]

function sectionFromHash(): Section {
  const value = window.location.hash.replace(/^#\/?/, '') as Section
  return SECTIONS.includes(value) ? value : 'resume'
}

function cachedActivePack(): OfflineRepairPack | null {
  const sessionId = activeRepairSessionId()
  return sessionId ? loadCachedOfflineRepairPack(null, sessionId) : null
}

export default function OfflineBootstrap({ children }: { children: ReactNode }) {
  const [networkOffline, setNetworkOffline] = useState(() => navigator.onLine === false)
  const [pack, setPack] = useState<OfflineRepairPack | null>(() => cachedActivePack())
  const [section, setSection] = useState<Section>(sectionFromHash)

  useEffect(() => {
    const online = () => setNetworkOffline(false)
    const offline = () => {
      setPack(cachedActivePack())
      setNetworkOffline(true)
    }
    const authCleared = () => setPack(null)
    const hash = () => setSection(sectionFromHash())
    window.addEventListener('online', online)
    window.addEventListener('offline', offline)
    window.addEventListener(AUTH_STATE_CLEARED_EVENT, authCleared)
    window.addEventListener('hashchange', hash)
    return () => {
      window.removeEventListener('online', online)
      window.removeEventListener('offline', offline)
      window.removeEventListener(AUTH_STATE_CLEARED_EVENT, authCleared)
      window.removeEventListener('hashchange', hash)
    }
  }, [])

  if (!networkOffline || !pack) return <>{children}</>

  return (
    <div className="offline-continuity-shell">
      <div className="offline-continuity-banner">
        <div>
          <strong>Offline repair pack · read only</strong>
          <span>Last sync {new Date(pack.generated_at).toLocaleString()} · definition v{pack.repair_definition_version} · reconnects automatically</span>
        </div>
      </div>
      <nav className="offline-continuity-nav" aria-label="Offline repair navigation">
        {SECTIONS.map((item) => (
          <button key={item} type="button" onClick={() => { window.location.hash = `#/${item}`; setSection(item) }}>
            {item === 'resume' ? 'Overview' : item === 'log' ? 'Repair log' : item}
          </button>
        ))}
      </nav>
      <OfflineRepairWorkspace pack={pack} section={section} />
    </div>
  )
}
