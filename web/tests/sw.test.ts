// Runs public/sw.js against a minimal fake of the service worker environment.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { beforeEach, describe, expect, it } from 'vitest'

const source = readFileSync(fileURLToPath(new URL('../public/sw.js', import.meta.url)), 'utf8')
const ORIGIN = 'https://courtmate.example'

type Handler = (event: FakeEvent) => void

class FakeCache {
  entries = new Map<string, Response>()
  async addAll(paths: string[]) {
    for (const path of paths) this.entries.set(new URL(path, ORIGIN).href, new Response(`shell:${path}`))
  }
  async put(key: string | Request, response: Response) {
    this.entries.set(typeof key === 'string' ? new URL(key, ORIGIN).href : key.url, response)
  }
}

class FakeEvent {
  response: Promise<Response> | undefined
  settled: Promise<unknown> | undefined
  constructor(readonly request: { url: string; method: string; mode: string }) {}
  respondWith(value: Promise<Response>) {
    this.response = Promise.resolve(value)
  }
  waitUntil(value: Promise<unknown>) {
    this.settled = value
  }
}

function boot(fetchImpl: (request: { url: string }) => Promise<Response>) {
  const handlers: Record<string, Handler> = {}
  const stores = new Map<string, FakeCache>()
  const caches = {
    open: async (name: string) => {
      if (!stores.has(name)) stores.set(name, new FakeCache())
      return stores.get(name) as FakeCache
    },
    keys: async () => [...stores.keys()],
    delete: async (name: string) => stores.delete(name),
    match: async (key: string | { url: string }) => {
      const href = typeof key === 'string' ? new URL(key, ORIGIN).href : key.url
      for (const store of stores.values()) if (store.entries.has(href)) return store.entries.get(href)?.clone()
      return undefined
    },
  }
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, handler: Handler) => (handlers[type] = handler),
    skipWaiting: async () => undefined,
    clients: { claim: async () => undefined },
  }
  new Function('self', 'caches', 'fetch', source)(self, caches, fetchImpl)
  return { handlers, stores, caches }
}

function request(path: string, init: Partial<{ method: string; mode: string }> = {}) {
  return { url: path.startsWith('http') ? path : `${ORIGIN}${path}`, method: 'GET', mode: 'no-cors', ...init }
}

describe('service worker', () => {
  let online = true
  let worker: ReturnType<typeof boot>

  beforeEach(async () => {
    online = true
    worker = boot(async (req) => {
      if (!online) throw new TypeError('offline')
      return new Response(`network:${new URL(req.url).pathname}`)
    })
    const install = new FakeEvent(request('/'))
    worker.handlers.install(install)
    await install.settled
  })

  it('precaches the app shell on install', async () => {
    const shell = worker.stores.get('courtmate-shell-v1')
    expect([...(shell?.entries.keys() ?? [])].map((href) => new URL(href).pathname)).toEqual(['/', '/manifest.webmanifest', '/favicon.svg', '/icons/icon-192.png'])
  })

  it('removes caches from older versions on activate', async () => {
    await worker.caches.open('courtmate-shell-v0')
    const activate = new FakeEvent(request('/'))
    worker.handlers.activate(activate)
    await activate.settled
    expect(await worker.caches.keys()).toEqual(['courtmate-shell-v1'])
  })

  it('never touches the API, other origins or writes', () => {
    for (const untouched of [
      request('https://courtmate-api.example/api/v1/auth/me'),
      request('https://tile.openstreetmap.org/5/1/2.png'),
      request('/assets/app.js', { method: 'POST' }),
      request('/some-unknown-file.json'),
    ]) {
      const event = new FakeEvent(untouched)
      worker.handlers.fetch(event)
      expect(event.response).toBeUndefined()
    }
  })

  it('serves pages from the network, and the saved shell when offline', async () => {
    const live = new FakeEvent(request('/venues/demo', { mode: 'navigate' }))
    worker.handlers.fetch(live)
    expect(await (await live.response)?.text()).toBe('network:/venues/demo')

    online = false
    const offline = new FakeEvent(request('/play', { mode: 'navigate' }))
    worker.handlers.fetch(offline)
    expect((await offline.response)?.ok).toBe(true)
  })

  it('caches hashed build assets after the first download', async () => {
    const first = new FakeEvent(request('/assets/index-abc123.js'))
    worker.handlers.fetch(first)
    expect(await (await first.response)?.text()).toBe('network:/assets/index-abc123.js')
    await new Promise((resolve) => setTimeout(resolve, 0))

    online = false
    const again = new FakeEvent(request('/assets/index-abc123.js'))
    worker.handlers.fetch(again)
    expect(await (await again.response)?.text()).toBe('network:/assets/index-abc123.js')
  })
})
