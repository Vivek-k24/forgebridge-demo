export function registerPartGraphServiceWorker(): void {
  if (!('serviceWorker' in navigator)) return
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
      // Offline continuity still works in the open tab when service workers are unavailable.
    })
  }, { once: true })
}
