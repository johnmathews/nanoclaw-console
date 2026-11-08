// Release 2's actions on their pages (W15): the buttons a task and a group offer, the
// ConfirmDialog's words, focus and keyboard, the one POST each confirm sends, and what the page
// says afterwards. No browser alert or confirm is ever used.
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import {
  actionAnswer,
  auditEmpty,
  auditUnwritable,
  auditView,
  GROUP_IDS,
  groupsView,
  PAUSED_TASK,
  PLANTED_MARK,
  TASKS,
  taskDetail,
} from '../../fixtures/api'
import { mountApp, reply, text, useClock, type Answers } from '../../__tests__/mountApp'

const PENDING = TASKS[0]!

function dialog(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[role="alertdialog"]')
}

function dialogText(selector: string): string {
  return document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim() ?? ''
}

async function click(el: Element | null): Promise<void> {
  if (!el) throw new Error('nothing to click')
  ;(el as HTMLElement).click()
  await flushPromises()
}

type FetchMock = Mock<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>

function posts(fetchMock: FetchMock): [string, RequestInit][] {
  return fetchMock.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === 'POST')
    .map(([input, init]) => [String(input), init as RequestInit])
}

function fetchMock(): FetchMock {
  return globalThis.fetch as unknown as FetchMock
}

async function openTask(id: string, extra: Answers = {}): Promise<VueWrapper> {
  return mountApp(`/tasks/${id}`, { [`/api/tasks/${id}`]: taskDetail(id), ...extra })
}

describe('a task’s actions', () => {
  beforeEach(() => {
    useClock()
    // The browser's own dialogs are never used: any call fails the test that made it.
    const refuse = (name: string) =>
      vi.fn<(message?: string) => never>(() => {
        throw new Error(`window.${name} was called`)
      })
    vi.stubGlobal('alert', refuse('alert'))
    vi.stubGlobal('confirm', refuse('confirm'))
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('a paused task offers Resume and Run now; a scheduled one Pause and Run now', async () => {
    let wrapper = await openTask(PAUSED_TASK.id)
    expect(wrapper.findAll('[role="group"] button').map((b) => b.text())).toEqual([
      'Resume',
      'Run now',
    ])
    expect(wrapper.text()).not.toContain('Asking the console’s API') // the task is loaded
    wrapper.unmount()
    document.body.innerHTML = ''
    wrapper = await openTask(PENDING.id)
    expect(wrapper.findAll('[role="group"] button').map((b) => b.text())).toEqual([
      'Pause',
      'Run now',
    ])
    expect(wrapper.find('#action-toggle').attributes('aria-haspopup')).toBe('dialog')
  })

  it('a task the API cannot find offers nothing', async () => {
    const wrapper = await mountApp('/tasks/task-gone', { '/api/tasks/task-gone': 404 })
    expect(wrapper.find('[role="group"]').exists()).toBe(false)
  })

  it('resume of the overdue task names it, its state, and that it runs once now', async () => {
    const wrapper = await openTask(PAUSED_TASK.id)
    await click(wrapper.find('#action-toggle').element)
    const box = dialog()!
    expect(box).not.toBeNull()
    expect(box.getAttribute('aria-modal')).toBe('true')
    expect(dialogText('[data-slot="confirm-title"]')).toBe('Resume documentation-summary?')
    expect(dialogText('#confirm-state')).toBe(
      'Now: paused. Its next run was due 27 May at 09:03 CEST.',
    )
    expect(dialogText('#confirm-warning')).toContain('runs once now')
    // aria-labelledby and aria-describedby point at the title and the facts.
    expect(document.getElementById(box.getAttribute('aria-labelledby')!)?.textContent).toBe(
      'Resume documentation-summary?',
    )
    expect(document.getElementById(box.getAttribute('aria-describedby')!)?.textContent).toContain(
      'Now: paused.',
    )
    expect(document.activeElement?.id).toBe('confirm-cancel')
    expect(posts(fetchMock())).toEqual([])
  })

  it('Cancel and Escape close it without asking the API', async () => {
    const wrapper = await openTask(PAUSED_TASK.id)
    const opener = wrapper.find('#action-toggle').element as HTMLElement
    opener.focus()
    await click(opener)
    await click(document.getElementById('confirm-cancel'))
    expect(dialog()).toBeNull()
    expect(document.activeElement).toBe(opener) // focus goes back to the control that asked
    await click(opener)
    document.activeElement!.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
    )
    await flushPromises()
    expect(dialog()).toBeNull()
    expect(posts(fetchMock())).toEqual([])
  })

  it('confirm sends one POST the CSRF guard accepts, then refreshes and says what happened', async () => {
    const path = `/api/tasks/${PAUSED_TASK.id}/resume`
    const wrapper = await openTask(PAUSED_TASK.id, { [`POST ${path}`]: actionAnswer('resume') })
    const gets = () => fetchMock().mock.calls.filter(([i]) => String(i).endsWith(PAUSED_TASK.id))
    const before = gets().length
    await click(wrapper.find('#action-toggle').element)
    await click(document.getElementById('confirm-act'))
    const sent = posts(fetchMock())
    expect(sent).toHaveLength(1)
    const [url, init] = sent[0]!
    expect(url).toBe(path)
    expect(init.body).toBe('{}')
    expect(init.headers).toMatchObject({
      'Content-Type': 'application/json',
      'X-Console-Action': '1',
    })
    expect(init.credentials).toBe('same-origin')
    expect(dialog()).toBeNull()
    expect(text(wrapper, '#action-result')).toBe('Resumed. It runs on its schedule again.')
    expect(wrapper.find('#action-result').attributes('data-tone')).toBe('success')
    expect(gets().length).toBe(before + 1) // the page read the task again
    expect(wrapper.text()).not.toContain('Asking the console’s API')
  })

  it('already in that state is said in plain words', async () => {
    const path = `/api/tasks/${PENDING.id}/pause`
    const wrapper = await openTask(PENDING.id, {
      [`POST ${path}`]: actionAnswer('pause', 'already_in_state'),
    })
    await click(wrapper.find('#action-toggle').element)
    await click(document.getElementById('confirm-act'))
    expect(text(wrapper, '#action-result')).toBe('It was already paused, so nothing changed.')
    expect(wrapper.find('#action-result').attributes('data-tone')).toBe('info')
  })

  it('run warns about tokens and the schedule; a refusal stays in the dialog', async () => {
    const path = `/api/tasks/${PAUSED_TASK.id}/run`
    const wrapper = await openTask(PAUSED_TASK.id, {
      [`POST ${path}`]: reply(503, actionAnswer('run', 'audit_unavailable')),
    })
    await click(wrapper.find('#action-run').element)
    expect(dialogText('[data-slot="confirm-title"]')).toBe('Run documentation-summary now?')
    expect(dialogText('#confirm-warning')).toBe(
      'A run spends tokens; it does not change the schedule.',
    )
    await click(document.getElementById('confirm-act'))
    expect(dialog()).not.toBeNull()
    expect(dialogText('#confirm-error')).toBe(
      'The console can’t write its audit log, so it didn’t act. Nothing changed.',
    )
    expect(wrapper.find('#action-result').exists()).toBe(false)
    // Opening it again starts without the old error.
    await click(document.getElementById('confirm-cancel'))
    await click(wrapper.find('#action-run').element)
    expect(document.getElementById('confirm-error')).toBeNull()
  })

  it('while the POST runs the verb says so, and a second confirm sends nothing', async () => {
    const path = `/api/tasks/${PAUSED_TASK.id}/run`
    let release: (r: Response) => void = () => {}
    const wrapper = await openTask(PAUSED_TASK.id)
    const original = fetchMock().getMockImplementation()!
    fetchMock().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'POST'
        ? new Promise<Response>((resolve) => (release = resolve))
        : original(input, init),
    )
    await click(wrapper.find('#action-run').element)
    await click(document.getElementById('confirm-act'))
    const act = document.getElementById('confirm-act')!
    expect(act.getAttribute('aria-busy')).toBe('true')
    expect(act.textContent?.trim()).toBe('Queuing…')
    await click(act)
    // Escape does nothing while it runs.
    act.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(dialog()).not.toBeNull()
    expect(posts(fetchMock()).map(([u]) => u)).toEqual([path])
    release(new Response(JSON.stringify(actionAnswer('run'))))
    await flushPromises()
    expect(dialog()).toBeNull()
    expect(text(wrapper, '#action-result')).toMatch(/^One run is queued/)
  })

  it('a network failure and an ended sign-in are said in the dialog', async () => {
    const path = `/api/tasks/${PAUSED_TASK.id}/run`
    const wrapper = await openTask(PAUSED_TASK.id, { [`POST ${path}`]: new TypeError('offline') })
    await click(wrapper.find('#action-run').element)
    await click(document.getElementById('confirm-act'))
    expect(dialogText('#confirm-error')).toContain('Couldn’t reach the console’s API')
  })

  it('a bare 403 reads as an ended sign-in; an unknown answer says so', async () => {
    const path = `/api/tasks/${PAUSED_TASK.id}/run`
    const wrapper = await openTask(PAUSED_TASK.id, { [`POST ${path}`]: 403 })
    await click(wrapper.find('#action-run').element)
    await click(document.getElementById('confirm-act'))
    expect(dialogText('#confirm-error')).toContain('sign-in may have ended')
    wrapper.unmount()
    document.body.innerHTML = ''
    const other = await openTask(PAUSED_TASK.id, { [`POST ${path}`]: 500 })
    await click(other.find('#action-run').element)
    await click(document.getElementById('confirm-act'))
    expect(dialogText('#confirm-error')).toContain('doesn’t know (500)')
  })

  it('an answer whose body is not JSON is unexpected', async () => {
    const path = `/api/tasks/${PAUSED_TASK.id}/run`
    const wrapper = await openTask(PAUSED_TASK.id)
    const original = fetchMock().getMockImplementation()!
    fetchMock().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'POST' ? new Response('<html>', { status: 502 }) : original(input, init),
    )
    await click(wrapper.find('#action-run').element)
    await click(document.getElementById('confirm-act'))
    expect(dialogText('#confirm-error')).toContain('(502)')
    expect(posts(fetchMock()).map(([u]) => u)).toEqual([path])
  })
})

describe('a group’s restart', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('warns that it interrupts a running turn, and says how many it restarted', async () => {
    const id = GROUP_IDS.main
    const path = `/api/groups/${id}/restart`
    const wrapper = await mountApp(`/groups/${id}`, {
      '/api/groups': groupsView(),
      [`POST ${path}`]: actionAnswer('restart'),
    })
    expect(wrapper.find('#action-restart').text()).toBe('Restart')
    await click(wrapper.find('#action-restart').element)
    expect(dialogText('[data-slot="confirm-title"]')).toBe('Restart main-group?')
    expect(dialogText('#confirm-state')).toBe('Now: one of its six sessions is running.')
    expect(dialogText('#confirm-warning')).toContain('interrupts a running turn')
    await click(document.getElementById('confirm-act'))
    expect(posts(fetchMock()).map(([u]) => u)).toEqual([path])
    expect(text(wrapper, '#action-result')).toBe('Restarted one container.')
    expect(wrapper.text()).not.toContain('Asking the console’s API')
  })

  it('an unknown group offers no restart', async () => {
    const wrapper = await mountApp('/groups/ag-nope', { '/api/groups': groupsView() })
    expect(wrapper.find('#action-restart').exists()).toBe(false)
  })
})

describe('the audit page', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('is in the navigation and lists every attempt, newest first', async () => {
    const wrapper = await mountApp('/audit', { '/api/audit': auditView() })
    expect(text(wrapper, 'h1')).toBe('Audit log')
    expect(document.title).toBe('Audit log · NanoClaw console')
    expect(wrapper.find('#nav-audit').attributes('aria-current')).toBe('page')
    expect(text(wrapper, '#audit-answer')).toBe(
      'Six attempts recorded; the last today at 15:25 CET.',
    )
    expect(wrapper.findAll('#audit-list > li')).toHaveLength(6)
    expect(wrapper.find('#audit-0').attributes('data-result')).toBe('done')
    expect(text(wrapper, '#audit-0')).toContain(`Restart ${GROUP_IDS.main}`)
    expect(text(wrapper, '#audit-0-result')).toBe('Done; one container restarted')
    expect(text(wrapper, '#audit-0-who')).toContain('john@example.com')
    expect(text(wrapper, '#audit-0-who')).toContain('ray 8c1d2e3f4a5b6c7d-AMS')
    expect(wrapper.find('#audit-0 a').attributes('href')).toBe(`/groups/${GROUP_IDS.main}`)
    expect(text(wrapper, '#audit-3-result')).toBe(
      'Refused: it did not come from the console’s own address',
    )
    expect(wrapper.find('#audit-3 [data-tone]').attributes('data-tone')).toBe('error')
    expect(text(wrapper, '#audit-5')).toContain('an id the console refused to write down')
    expect(document.documentElement.outerHTML).not.toContain(PLANTED_MARK)
  })

  it('says when nothing was done, when the log is cut and when it cannot be written', async () => {
    let wrapper = await mountApp('/audit', { '/api/audit': auditEmpty() })
    expect(text(wrapper, '#audit-answer')).toBe('Nothing has been done from the console yet.')
    expect(text(wrapper, '#audit-empty')).toBe('Nothing recorded yet.')
    wrapper.unmount()
    document.body.innerHTML = ''
    wrapper = await mountApp('/audit', { '/api/audit': auditUnwritable() })
    expect(text(wrapper, '#audit-unwritable')).toContain('refused until it can')
    wrapper.unmount()
    document.body.innerHTML = ''
    wrapper = await mountApp('/audit', { '/api/audit': { ...auditView(), truncated: true } })
    expect(text(wrapper, '#audit')).toContain('from the most recent part of the log')
    wrapper.unmount()
    document.body.innerHTML = ''
    wrapper = await mountApp('/audit', {
      '/api/audit': { ...auditEmpty(), available: false, writable: false },
    })
    expect(text(wrapper, '#audit-unreadable')).toContain('Couldn’t read the audit log')
    expect(wrapper.find('#audit').exists()).toBe(false)
  })

  it('an unreachable API shows the banner, not an empty log', async () => {
    const wrapper = await mountApp('/audit', { '/api/audit': new TypeError('offline') })
    expect(wrapper.find('#audit-answer').exists()).toBe(false)
    expect(wrapper.find('#page-banner').exists()).toBe(true)
  })
})
