import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useOverviewStore } from '../overview'

function respond(status: number, body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  )
}

describe('the overview store', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.unstubAllGlobals())

  it('starts loading', () => {
    expect(useOverviewStore().state).toBe('loading')
  })

  it('holds the overview the API returns', async () => {
    respond(200, { status: 'scaffold' })
    const store = useOverviewStore()
    await store.load()
    expect(store.state).toBe('ready')
    expect(store.overview).toEqual({ status: 'scaffold' })
    expect(fetch).toHaveBeenCalledWith('/api/overview', expect.anything())
  })

  it('is in error when the API refuses', async () => {
    respond(403, { detail: 'Forbidden' })
    const store = useOverviewStore()
    await store.load()
    expect(store.state).toBe('error')
    expect(store.overview).toBeNull()
  })

  it('is in error when the network fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    const store = useOverviewStore()
    await store.load()
    expect(store.state).toBe('error')
  })
})
