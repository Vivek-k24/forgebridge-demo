const SHELL_CACHE = 'partgraph-shell-v1'
const SHELL_ENTRIES = ['/', '/index.html']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ENTRIES))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith('partgraph-shell-') && key !== SHELL_CACHE)
          .map((key) => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('message', (event) => {
  if (event.data?.type !== 'CACHE_APP_SHELL_ASSETS' || !Array.isArray(event.data.urls)) return
  const safeUrls = event.data.urls.filter((value) => {
    if (typeof value !== 'string') return false
    try {
      const url = new URL(value, self.location.origin)
      return url.origin === self.location.origin && !url.pathname.startsWith('/api/')
    } catch {
      return false
    }
  })
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(safeUrls)))
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone()
            caches.open(SHELL_CACHE).then((cache) => cache.put('/index.html', copy))
          }
          return response
        })
        .catch(async () => (
          await caches.match('/index.html')
          || await caches.match('/')
          || Response.error()
        )),
    )
    return
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached
      return fetch(request).then((response) => {
        if (response.ok && response.type === 'basic') {
          const copy = response.clone()
          caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy))
        }
        return response
      })
    }),
  )
})
