import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const origin = 'https://partgraph.test'
const source = readFileSync(new URL('../public/sw.js', import.meta.url), 'utf8')
const handlers = new Map()
let offline = false

function normalizeRequest(input) {
  const raw = typeof input === 'string' ? input : input.url
  return new URL(raw, origin).href
}

async function networkFetch(input) {
  if (offline) throw new Error('network offline')
  const url = normalizeRequest(input)
  return new Response(`network:${url}`, { status: 200 })
}

class FakeCache {
  constructor() {
    this.entries = new Map()
  }

  async addAll(values) {
    const responses = await Promise.all(values.map(async (value) => [
      normalizeRequest(value),
      await networkFetch(value),
    ]))
    for (const [url, response] of responses) this.entries.set(url, response.clone())
  }

  async match(input) {
    const response = this.entries.get(normalizeRequest(input))
    return response ? response.clone() : undefined
  }

  async put(input, response) {
    this.entries.set(normalizeRequest(input), response.clone())
  }

  async keys() {
    return [...this.entries.keys()].map((url) => ({ url }))
  }

  async delete(input) {
    return this.entries.delete(normalizeRequest(input))
  }
}

const stores = new Map()
const caches = {
  async open(name) {
    if (!stores.has(name)) stores.set(name, new FakeCache())
    return stores.get(name)
  },
  async keys() {
    return [...stores.keys()]
  },
  async delete(name) {
    return stores.delete(name)
  },
}

const self = {
  location: { origin },
  clients: { claim: async () => undefined },
  skipWaiting: async () => undefined,
  addEventListener(type, handler) {
    handlers.set(type, handler)
  },
}

vm.runInNewContext(source, {
  URL,
  Response,
  caches,
  fetch: networkFetch,
  self,
})

async function dispatchWaitUntil(type, event) {
  let pending
  handlers.get(type)({
    ...event,
    waitUntil(value) {
      pending = Promise.resolve(value)
    },
  })
  if (pending) await pending
}

async function dispatchFetch(request) {
  let responsePromise
  handlers.get('fetch')({
    request,
    respondWith(value) {
      responsePromise = Promise.resolve(value)
    },
  })
  return responsePromise
}

await dispatchWaitUntil('install', {})
const oldCache = await caches.open('partgraph-shell-v1')
await oldCache.addAll(['/legacy-release.js'])
await dispatchWaitUntil('activate', {})
assert.deepEqual(await caches.keys(), ['partgraph-shell-v2'])

await dispatchWaitUntil('message', {
  data: {
    type: 'CACHE_APP_SHELL_ASSETS',
    urls: [
      `${origin}/assets/index-old.js`,
      `${origin}/assets/index-old.css`,
      `${origin}/api/v1/private`,
      'https://example.com/cross-origin.js',
    ],
  },
})

const shell = await caches.open('partgraph-shell-v2')
let urls = (await shell.keys()).map((request) => request.url).sort()
assert.deepEqual(urls, [
  `${origin}/`,
  `${origin}/assets/index-old.css`,
  `${origin}/assets/index-old.js`,
  `${origin}/index.html`,
].sort())

const privateResponse = await dispatchFetch({
  method: 'GET',
  mode: 'same-origin',
  url: `${origin}/account/private`,
})
assert.equal(await privateResponse.text(), `network:${origin}/account/private`)
assert.equal(await shell.match(`${origin}/account/private`), undefined)

const apiResponse = await dispatchFetch({
  method: 'GET',
  mode: 'same-origin',
  url: `${origin}/api/v1/repair-sessions/private`,
})
assert.equal(apiResponse, undefined)

await dispatchWaitUntil('message', {
  data: {
    type: 'CACHE_APP_SHELL_ASSETS',
    urls: [
      `${origin}/assets/index-new.js`,
      `${origin}/assets/index-new.css`,
    ],
  },
})

urls = (await shell.keys()).map((request) => request.url).sort()
assert.deepEqual(urls, [
  `${origin}/`,
  `${origin}/assets/index-new.css`,
  `${origin}/assets/index-new.js`,
  `${origin}/index.html`,
].sort())
assert.equal(await shell.match(`${origin}/assets/index-old.js`), undefined)
assert.equal(await shell.match(`${origin}/assets/index-old.css`), undefined)

offline = true
const offlineNavigation = await dispatchFetch({
  method: 'GET',
  mode: 'navigate',
  url: `${origin}/repairs/current`,
})
assert.equal(offlineNavigation.status, 200)
assert.match(await offlineNavigation.text(), /^network:https:\/\/partgraph\.test\/index\.html$/)

console.log('Service-worker cache lifecycle contract passed.')
