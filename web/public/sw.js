const SHELL_CACHE = 'partgraph-shell-v2'
const SHELL_ENTRIES = ['/', '/index.html']

function safeShellUrls(values) {
  const urls = new Set(SHELL_ENTRIES)
  for (const value of values) {
    if (typeof value !== 'string') continue
    try {
      const url = new URL(value, self.location.origin)
      if (url.origin === self.location.origin && !url.pathname.startsWith('/api/')) {
        urls.add(url.href)
      }
    } catch {
      // Ignore malformed shell manifest entries.
    }
  }
  return [...urls]
}

function absoluteCacheKey(value) {
  return new URL(value, self.location.origin).href
}

async function synchronizeShellCache(values) {
  const urls = safeShellUrls(values)
  const keep = new Set(urls.map(absoluteCacheKey))
  const cache = await caches.open(SHELL_CACHE)

  // Populate the complete replacement shell before removing the previous one.
  await cache.addAll(urls)

  const cachedRequests = await cache.keys()
  await Promise.all(
    cachedRequests
      .filter((request) => !keep.has(request.url))
      .map((request) => cache.delete(request)),
  )
}

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
  event.waitUntil(synchronizeShellCache(event.data.urls))
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
        .catch(async () => {
          const cache = await caches.open(SHELL_CACHE)
          return await cache.match('/index.html')
            || await cache.match('/')
            || Response.error()
        }),
    )
    return
  }

  event.respondWith(
    caches.open(SHELL_CACHE).then(async (cache) => (
      await cache.match(request)
      || fetch(request)
    )),
  )
})
