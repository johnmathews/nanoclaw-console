import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { problemsEveryKind, problemsView, STALE_APPROVAL_ID } from '../../fixtures/api'
import { mountApp, text, useClock } from '../../__tests__/mountApp'
import type { ProblemsView } from '../../lib/types'

async function open(body: unknown = problemsView()) {
  return mountApp('/problems', { '/api/problems': body })
}

describe('the problems page', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('answers first', async () => {
    const wrapper = await open()
    expect(text(wrapper, 'h1')).toBe('Problems')
    expect(document.title).toBe('Problems · NanoClaw console')
    expect(text(wrapper, '#problems-answer')).toBe(
      'One error, six warnings and one note need a look.',
    )
  })

  it('keeps the API’s order and draws every item', async () => {
    const body = problemsView()
    const wrapper = await open(body)
    const items = wrapper.findAll('#problems > ul > li')
    expect(items.map((li) => li.find('p').text())).toEqual(body.items.map((i) => i.title))
  })

  it('draws every kind the contract has, worst first, with links where the ref allows', async () => {
    const body = problemsEveryKind()
    const wrapper = await open(body)
    const items = wrapper.findAll('#problems > ul > li')
    expect(items).toHaveLength(body.items.length)
    expect(items.map((li) => li.attributes('id'))).toEqual(
      body.items.map((item, i) => `problem-${item.kind}-${i}`),
    )
    const links = wrapper.findAll('#problems a').map((a) => [a.text(), a.attributes('href')])
    expect(links).toEqual([
      ['See groups and channels', '/groups#channel-slack'],
      ['Open the task', '/tasks/task-1783504800000-mh4k2p'],
      ['See the approval', `/permissions#approval-${STALE_APPROVAL_ID}`],
      ['Open the task', '/tasks/task-1778399790530-f2euaw'],
      ['See groups and channels', '/groups#channel-mg-1780100000000-dr0p01'],
      ['Open the group', '/groups/ag-1779373702795-5wbiev'],
    ])
  })

  it('groups NanoClaw’s host log lines by message, with counts, first and last seen and a sample', async () => {
    const wrapper = await open()
    expect(text(wrapper, '#host-logs-summary')).toBe(
      '8 errors and 13 warnings in the last 24 hours, in four groups by message.',
    )
    const groups = wrapper.findAll('#host-log-groups > li')
    expect(groups).toHaveLength(4)
    expect(groups[0]!.attributes('data-level')).toBe('ERROR')
    expect(text(wrapper, '#log-group-0')).toContain('Container exited with error')
    expect(text(wrapper, '#log-group-0-count')).toBe('3 times')
    expect(text(wrapper, '#log-group-0-seen')).toBe(
      'First today at 03:11 CET, last today at 14:58 CET (32 minutes ago)',
    )
    expect(text(wrapper, '#log-group-0-sample')).toContain('authorization=***')
    expect(text(wrapper, '#log-group-2')).toContain('Warning')
  })

  it('says when the log was cut, empty, or could not be read', async () => {
    const cut = problemsView()
    cut.host_logs!.truncated = true
    const w1 = await open(cut)
    expect(text(w1, '#host-logs-truncated')).toBe(
      'More lines matched than the console reads (2000); these groups are from the newest.',
    )
    w1.unmount()
    document.body.innerHTML = ''

    const quiet = problemsView()
    quiet.host_logs = { ...quiet.host_logs!, errors: 0, warnings: 0, groups: [] }
    const w2 = await open(quiet)
    expect(text(w2, '#host-logs-summary')).toBe('No errors or warnings in the last 24 hours.')
    w2.unmount()
    document.body.innerHTML = ''

    const failed: ProblemsView = {
      ...problemsView(),
      host_logs: null,
      sources: {
        broker: { ok: true, errors: {} },
        loki: { ok: false, errors: { host_logs: 'unavailable' } },
      },
    }
    const w3 = await open(failed)
    expect(text(w3, '#host-logs-unread')).toBe(
      'Couldn’t read NanoClaw’s host logs from Loki, so they are not shown.',
    )
    expect(text(w3, '#page-sources')).toContain('NanoClaw’s host logs in Loki')
  })

  it('says nothing needs a look when there are no items', async () => {
    const wrapper = await open({ ...problemsView(), items: [] })
    expect(text(wrapper, '#problems-answer')).toBe('Nothing needs a look.')
    expect(text(wrapper, '#problems')).toContain('Nothing needs a look.')
  })
})
