import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { overview, overviewDegraded, PAUSED_TASK } from '../../fixtures/api'
import { REFRESH_MS } from '../../composables/useApi'
import { mountApp, text, useClock } from '../../__tests__/mountApp'

async function open(body: unknown = overview()) {
  return mountApp('/', { '/api/overview': body })
}

describe('the overview', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('answers first: is Claude working, is NanoClaw running', async () => {
    const wrapper = await open()
    expect(text(wrapper, 'h1')).toBe('Overview')
    expect(text(wrapper, '#overview-answer')).toBe(
      'Claude is answering NanoClaw’s agents. NanoClaw is running.',
    )
  })

  it('shows Claude’s status in words beside the mark, with its reasons', async () => {
    const wrapper = await open()
    const badge = wrapper.find('#claude-status')
    expect(badge.attributes('data-status')).toBe('ok')
    expect(badge.text()).toContain('OK')
    expect(text(wrapper, '#claude-reasons')).toBe(
      'The last agent call to Claude succeeded (HTTP 200).',
    )
  })

  it('gives the last success, the auth failures and the probe', async () => {
    const wrapper = await open()
    expect(text(wrapper, '#claude-last-success')).toBe('today at 15:28 CET (two minutes ago)')
    expect(text(wrapper, '#claude-auth-failures')).toBe('None in the last hour, none in 24 hours')
    expect(text(wrapper, '#claude-agent-calls')).toBe('412')
    expect(text(wrapper, '#claude-probe')).toBe('OK, checked today at 15:26 CET (HTTP 400)')
  })

  it('counts auth failures and says when Claude is failing', async () => {
    const body = overview()
    body.claude.status = 'failing'
    body.claude.reasons = ['The last agent call to Claude was refused (HTTP 401).']
    body.claude.auth_failures_1h = 2
    body.claude.auth_failures_24h = 5
    body.claude.last_agent_call!.status = 401
    const wrapper = await open(body)
    expect(wrapper.find('#claude-status').attributes('data-status')).toBe('failing')
    expect(text(wrapper, '#claude-status')).toContain('Failing')
    expect(text(wrapper, '#claude-auth-failures')).toBe('2 in the last hour, 5 in 24 hours')
    expect(text(wrapper, '#overview-answer')).toContain('Claude is refusing NanoClaw’s token.')
  })

  it('says what it cannot see about Claude', async () => {
    const wrapper = await open(overviewDegraded())
    expect(wrapper.find('#claude-status').attributes('data-status')).toBe('unknown')
    expect(text(wrapper, '#claude-last-success')).toBe('None in the last 24 hours')
    expect(text(wrapper, '#claude-auth-failures')).toBe('Couldn’t read Loki')
    expect(text(wrapper, '#claude-probe')).toBe('No result from the probe')
  })

  it('shows NanoClaw’s channels, loop, queue, sessions and uptime', async () => {
    const wrapper = await open()
    expect(text(wrapper, '#nanoclaw-status')).toContain('Healthy')
    expect(text(wrapper, '#nanoclaw-uptime')).toBe('20 hours')
    const channels = wrapper.findAll('#nanoclaw-channels li').map((li) => li.text())
    expect(channels).toEqual(['cli Connected', 'slack Connected'])
    expect(text(wrapper, '#nanoclaw-loop')).toBe('Running')
    expect(text(wrapper, '#nanoclaw-queue')).toBe('1 active, 0 waiting')
    expect(text(wrapper, '#nanoclaw-sessions')).toBe('18 active')
  })

  it('says plainly when NanoClaw is not answering', async () => {
    const wrapper = await open(overviewDegraded())
    expect(text(wrapper, '#nanoclaw-not-answering')).toContain('NanoClaw is not answering.')
    expect(wrapper.find('#nanoclaw-channels').exists()).toBe(false)
  })

  it('labels the quota exactly as the API does: the host login, not NanoClaw’s token', async () => {
    const body = overview()
    const wrapper = await open(body)
    expect(text(wrapper, '#quota-label')).toBe(body.quota.label)
    expect(text(wrapper, '#quota-used')).toBe('39% used')
    expect(text(wrapper, '#quota-resets')).toBe('Resets Tuesday at 21:00 CET (in two days)')
  })

  it('keeps the label when the quota cannot be read', async () => {
    const wrapper = await open(overviewDegraded())
    expect(text(wrapper, '#quota-label')).toBe(overview().quota.label)
    expect(text(wrapper, '#quota-card')).toContain('Couldn’t read the quota.')
  })

  it('shows the counts, and which could not be read', async () => {
    const wrapper = await open(overviewDegraded())
    expect(text(wrapper, '#count-groups')).toBe('15')
    expect(text(wrapper, '#count-host-errors')).toBe('Couldn’t read')
  })

  it('lists the warnings, worst first, and links a task warning to its task', async () => {
    const wrapper = await open()
    const items = wrapper.findAll('#warnings li')
    expect(items).toHaveLength(4)
    expect(items[0]!.text()).toContain('Error')
    expect(items[0]!.text()).toContain('NanoClaw logged 8 errors in 24 hours')
    const task = wrapper.find('#warnings a[href^="/tasks/"]')
    expect(task.attributes('href')).toBe(`/tasks/${PAUSED_TASK.id}`)
  })

  it('says when there is nothing to look at', async () => {
    const body = overview()
    body.warnings = []
    const wrapper = await open(body)
    expect(text(wrapper, '#warnings')).toContain('Nothing needs a look.')
  })

  it('says when it was generated, and that it refreshes', async () => {
    const wrapper = await open()
    expect(text(wrapper, '#page-freshness')).toBe(
      'Updated just now, at 15:30 CET. Refreshes every 30 seconds.',
    )
  })

  it('names each failed read plainly', async () => {
    const wrapper = await open(overviewDegraded())
    const sources = text(wrapper, '#page-sources')
    expect(sources).toContain('Some reads failed, so parts of this page are empty.')
    expect(sources).toContain('Couldn’t read the quota: the broker took too long to answer.')
    expect(sources).toContain('Couldn’t read Claude’s traffic in Loki: Loki did not answer.')
  })

  it('refreshes every 30 seconds and keeps the last answer when a refresh fails', async () => {
    const wrapper = await open()
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockImplementation(async () => new Response('', { status: 502 }))
    await vi.advanceTimersByTimeAsync(REFRESH_MS)
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.find('#claude-status').exists()).toBe(true)
    expect(text(wrapper, '#page-banner')).toBe(
      'Couldn’t reach the console’s API, so this page shows what it had at 15:30 CET. It retries every 30 seconds.',
    )
  })

  it('says what to do when the API cannot be reached at all', async () => {
    const wrapper = await mountApp('/', { '/api/overview': new TypeError('Failed to fetch') })
    expect(text(wrapper, '#page-banner')).toBe(
      'Couldn’t reach the console’s API. It retries every 30 seconds.',
    )
  })

  it('says the sign-in may have ended on a 403', async () => {
    const wrapper = await mountApp('/', { '/api/overview': 403 })
    expect(text(wrapper, '#page-banner')).toBe(
      'The console refused this browser (HTTP 403). Your Cloudflare Access sign-in may have ended: reload the page to sign in again.',
    )
  })
})
