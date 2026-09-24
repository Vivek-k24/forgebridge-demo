import { useEffect, useId, useState } from 'react'
import './site-footer.css'

type FooterTopic = 'about' | 'privacy' | 'terms' | 'contact'

type TopicContent = {
  label: string
  title: string
  body: React.ReactNode
}

const TOPICS: Record<FooterTopic, TopicContent> = {
  about: {
    label: 'About',
    title: 'About PartGraph',
    body: (
      <>
        <p>PartGraph is a personal-project MVP for keeping vehicle identity, repair readiness, verified guidance, physical repair memory, and repair history connected in one workspace.</p>
        <p>When verified vehicle-specific information is unavailable, PartGraph is designed to keep that gap visible rather than invent a procedure or specification.</p>
      </>
    ),
  },
  privacy: {
    label: 'Privacy Policy',
    title: 'MVP Privacy Policy',
    body: (
      <>
        <p>PartGraph stores account identity, saved vehicles, equipment inventory, repair sessions, readiness state, repair notes, and user-added repair photos so the signed-in owner can resume work later.</p>
        <p>Authentication uses an HttpOnly session cookie. This browser may also store a device identifier, display preferences, the active repair identifier, and a privacy-minimized read-only offline repair pack. The offline pack excludes username and email.</p>
        <p>User repair data is scoped to the signed-in account. The hosted MVP relies on infrastructure providers to operate the application, database, and private media storage. The current product has no advertising or user-data-sale feature.</p>
      </>
    ),
  },
  terms: {
    label: 'Terms',
    title: 'MVP Terms of Use',
    body: (
      <>
        <p>PartGraph is an early personal-project MVP. It is provided for testing and informational use without a guarantee that every vehicle, repair, procedure, specification, or compatibility detail is complete.</p>
        <p>Vehicle repair can involve serious safety risks. Verify safety-critical instructions, torque values, fluids, electrical procedures, lifting points, and service requirements against authoritative service information or a qualified professional before acting.</p>
        <p>Do not treat an unsupported or missing PartGraph workflow as permission to improvise a repair. Where PartGraph marks a boundary or required external service, that boundary should remain in effect.</p>
      </>
    ),
  },
  contact: {
    label: 'Contact Us',
    title: 'Contact PartGraph',
    body: (
      <>
        <p>This MVP does not yet have a production support channel.</p>
        <p><strong>Placeholder email:</strong> <a href="mailto:support@partgraph.example">support@partgraph.example</a></p>
        <p>Replace this placeholder before any public or commercial launch.</p>
      </>
    ),
  },
}

export function SiteFooter({ variant = 'light' }: { variant?: 'light' | 'dark' }) {
  const [topic, setTopic] = useState<FooterTopic | null>(null)
  const titleId = useId()

  useEffect(() => {
    if (!topic) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setTopic(null)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [topic])

  const content = topic ? TOPICS[topic] : null

  return (
    <>
      <footer className={`site-footer site-footer--${variant}`}>
        <div className="site-footer__brand">
          <strong>PartGraph</strong>
          <span>Personal MVP · repair continuity</span>
        </div>
        <nav className="site-footer__links" aria-label="Product information">
          {(Object.keys(TOPICS) as FooterTopic[]).map((key) => (
            <a
              key={key}
              href={`#/${key}`}
              onClick={(event) => {
                event.preventDefault()
                setTopic(key)
              }}
            >
              {TOPICS[key].label}
            </a>
          ))}
        </nav>
        <span className="site-footer__meta">© 2026 PartGraph</span>
      </footer>

      {content && (
        <div
          className="site-footer-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) setTopic(null)
          }}
        >
          <section
            className="site-footer-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
          >
            <div className="site-footer-dialog__head">
              <div>
                <span>PARTGRAPH</span>
                <h2 id={titleId}>{content.title}</h2>
              </div>
              <button type="button" onClick={() => setTopic(null)} aria-label="Close information dialog">Close</button>
            </div>
            <div className="site-footer-dialog__body">
              {content.body}
              <small>Last updated September 24, 2026.</small>
            </div>
          </section>
        </div>
      )}
    </>
  )
}
