// Mounts the whole app at a route, with /api/* answered from a table (path → body, a bare status
// number for a refusal, or `reply(status, body)`; a POST is keyed `POST <path>`) and the clock at
// the fixtures' NOW. Not a spec: shared set-up.
import { vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory } from 'vue-router'
import App from '../App.vue'
import { createAppRouter } from '../router'
import { NOW } from '../fixtures/api'

export type Answers = Record<string, unknown>

/** An answer with a status other than 200 and a JSON body (an action's 409, 503, …). */
export class Reply {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {}
}

export function reply(status: number, body: unknown): Reply {
  return new Reply(status, body)
}

export function stubApi(answers: Answers) {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
    async (input, init) => {
      const method = init?.method ?? 'GET'
      const path = method === 'GET' ? String(input) : `${method} ${String(input)}`
      if (!(path in answers)) return new Response('{"error":"not_found"}', { status: 404 })
      const answer = answers[path]
      if (answer instanceof Error) throw answer
      if (answer instanceof Reply)
        return new Response(JSON.stringify(answer.body), { status: answer.status })
      if (typeof answer === 'number') return new Response('{}', { status: answer })
      return new Response(JSON.stringify(answer))
    },
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function useClock(): void {
  vi.useFakeTimers({ now: new Date(NOW) })
}

export async function mountApp(path: string, answers: Answers): Promise<VueWrapper> {
  stubApi(answers)
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}

/** The visible text of an element, whitespace collapsed. */
export function text(wrapper: VueWrapper, selector: string): string {
  const el = wrapper.find(selector)
  if (!el.exists()) throw new Error(`no element matches ${selector}`)
  return el.text().replace(/\s+/g, ' ').trim()
}
