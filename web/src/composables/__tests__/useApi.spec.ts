import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { REFRESH_MS, useApi } from '../useApi'

function respond(...answers: (() => Promise<Response>)[]) {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>()
  for (const answer of answers) fetchMock.mockImplementationOnce(answer)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const ok = (body: unknown) => async () => new Response(JSON.stringify(body))

function host(path = ref('/api/x')) {
  let api!: ReturnType<typeof useApi<{ n: number }>>
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useApi<{ n: number }>(path)
        return () => h('div')
      },
    }),
  )
  return { wrapper, api: () => api }
}

describe('useApi', () => {
  beforeEach(() => vi.useFakeTimers({ now: new Date('2026-11-08T14:30:00Z') }))
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('refreshes every 30 seconds through the backend', async () => {
    expect(REFRESH_MS).toBe(30_000)
    const fetchMock = respond(ok({ n: 1 }), ok({ n: 2 }))
    const { api } = host()
    await flushPromises()
    expect(api().data.value).toEqual({ n: 1 })
    expect(fetchMock).toHaveBeenCalledWith('/api/x', expect.anything())
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    await flushPromises()
    expect(api().data.value).toEqual({ n: 2 })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('keeps the last answer when a refresh fails, and says so', async () => {
    respond(ok({ n: 1 }), async () => new Response('', { status: 502 }))
    const { api } = host()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    await flushPromises()
    expect(api().data.value).toEqual({ n: 1 })
    expect(api().error.value).toEqual({ status: 502 })
    expect(api().checkedAt.value.toISOString()).toBe('2026-11-08T14:30:30.000Z')
  })

  it('reports a network failure as status null and clears it on the next answer', async () => {
    respond(
      async () => {
        throw new TypeError('Failed to fetch')
      },
      ok({ n: 3 }),
    )
    const { api } = host()
    await flushPromises()
    expect(api().error.value).toEqual({ status: null })
    expect(api().data.value).toBeNull()
    await api().refresh()
    expect(api().error.value).toBeNull()
    expect(api().data.value).toEqual({ n: 3 })
  })

  it('loads the new path at once when it changes, dropping the old answer', async () => {
    const fetchMock = respond(ok({ n: 1 }), ok({ n: 9 }))
    const path = ref('/api/a')
    const { api } = host(path)
    await flushPromises()
    path.value = '/api/b'
    await nextTick()
    expect(api().data.value).toBeNull()
    await flushPromises()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/b', expect.anything())
    expect(api().data.value).toEqual({ n: 9 })
  })

  it('stops refreshing when its page goes away', async () => {
    const fetchMock = respond(ok({ n: 1 }), ok({ n: 2 }))
    const { wrapper } = host()
    await flushPromises()
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(REFRESH_MS * 3)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('ignores an answer for a path it has left', async () => {
    let release!: (r: Response) => void
    respond(() => new Promise<Response>((resolve) => (release = resolve)), ok({ n: 2 }))
    const path = ref('/api/a')
    const { api } = host(path)
    path.value = '/api/b'
    await flushPromises()
    release(new Response(JSON.stringify({ n: 1 })))
    await flushPromises()
    expect(api().data.value).toEqual({ n: 2 })
  })
})
