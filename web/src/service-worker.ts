function currentShellAssets(): string[] {
  const urls = new Set<string>(['/', '/index.html'])
  document.querySelectorAll<HTMLScriptElement>('script[src]').forEach((element) => {
    if (element.src.startsWith(window.location.origin)) urls.add(element.src)
  })
  document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"][href]').forEach((element) => {
    if (element.href.startsWith(window.location.origin)) urls.add(element.href)
  })
  return [...urls]
}

export function registerPartGraphServiceWorker(): void {
  if (!('serviceWorker' in navigator)) return
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(() => navigator.serviceWorker.ready)
      .then((registration) => {
        registration.active?.postMessage({
          type: 'CACHE_APP_SHELL_ASSETS',
          urls: currentShellAssets(),
        })
      })
      .catch(() => {
        // Offline continuity still works in the open tab when service workers are unavailable.
      })
  }, { once: true })
}
