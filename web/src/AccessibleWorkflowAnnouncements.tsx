import { useEffect, useRef, useState } from 'react'
import './accessible-workflow-announcements.css'

type AnnouncementProps = {
  message: string
}

export function StatusMessage({ message }: AnnouncementProps) {
  return (
    <div className="partgraph-sr-live" role="status" aria-live="polite" aria-atomic="true">
      {message}
    </div>
  )
}

export function ErrorAlert({ message }: AnnouncementProps) {
  return (
    <div className="partgraph-sr-live" role="alert" aria-live="assertive" aria-atomic="true">
      {message}
    </div>
  )
}

const STATUS_SELECTOR = [
  '.workspace-alert--success',
  '.memory-alert--success',
  '.repair-alert--success',
].join(',')

const ERROR_SELECTOR = [
  '.workspace-alert--error',
  '.memory-alert--error',
  '.repair-alert--error',
].join(',')

const AUDITED_MESSAGE_SELECTOR = `${STATUS_SELECTOR},${ERROR_SELECTOR}`

function alreadyLive(element: Element): boolean {
  return Boolean(element.closest('[role="status"],[role="alert"],[aria-live]'))
}

export default function AccessibleWorkflowAnnouncements() {
  const [statusMessage, setStatusMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const seenText = useRef(new WeakMap<Element, string>())
  const statusTimer = useRef<number | null>(null)
  const errorTimer = useRef<number | null>(null)

  useEffect(() => {
    function queueAnnouncement(kind: 'status' | 'error', text: string) {
      if (kind === 'error') {
        if (errorTimer.current !== null) window.clearTimeout(errorTimer.current)
        setErrorMessage('')
        errorTimer.current = window.setTimeout(() => {
          setErrorMessage(text)
          errorTimer.current = null
        }, 0)
        return
      }

      if (statusTimer.current !== null) window.clearTimeout(statusTimer.current)
      setStatusMessage('')
      statusTimer.current = window.setTimeout(() => {
        setStatusMessage(text)
        statusTimer.current = null
      }, 0)
    }

    function inspectCandidate(candidate: Element) {
      if (alreadyLive(candidate)) return
      const text = candidate.textContent?.trim()
      if (!text || seenText.current.get(candidate) === text) return
      seenText.current.set(candidate, text)
      queueAnnouncement(candidate.matches(ERROR_SELECTOR) ? 'error' : 'status', text)
    }

    function inspectElement(element: Element) {
      if (element.matches(AUDITED_MESSAGE_SELECTOR)) inspectCandidate(element)
      element.querySelectorAll(AUDITED_MESSAGE_SELECTOR).forEach(inspectCandidate)
    }

    document.querySelectorAll(AUDITED_MESSAGE_SELECTOR).forEach(inspectCandidate)

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'characterData') {
          const parent = mutation.target.parentElement
          if (parent) inspectElement(parent)
          continue
        }
        for (const node of mutation.addedNodes) {
          if (node instanceof Element) inspectElement(node)
          else if (node.parentElement) inspectElement(node.parentElement)
        }
      }
    })

    observer.observe(document.body, { childList: true, characterData: true, subtree: true })
    return () => {
      observer.disconnect()
      if (statusTimer.current !== null) window.clearTimeout(statusTimer.current)
      if (errorTimer.current !== null) window.clearTimeout(errorTimer.current)
    }
  }, [])

  return (
    <>
      <StatusMessage message={statusMessage} />
      <ErrorAlert message={errorMessage} />
    </>
  )
}
