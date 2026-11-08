import { describe, expect, it } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import ClaudeCard from '../overview/ClaudeCard.vue'
import NanoclawCard from '../overview/NanoclawCard.vue'
import QuotaCard from '../overview/QuotaCard.vue'
import PageStatus from '../PageStatus.vue'
import TaskStatus from '../TaskStatus.vue'
import WarningList from '../WarningList.vue'
import { NOW, overview, PAUSED_TASK } from '../../fixtures/api'
import type { NanoclawHealth, Quota } from '../../lib/types'

const now = new Date(NOW)
const stubs = { RouterLink: RouterLinkStub }
const squash = (s: string) => s.replace(/\s+/g, ' ').trim()

function nanoclaw(changes: Partial<Extract<NanoclawHealth, { available: true }>>): NanoclawHealth {
  const base = overview().nanoclaw as Extract<NanoclawHealth, { available: true }>
  return { ...base, ...changes }
}

describe('the NanoClaw card', () => {
  it('says when NanoClaw calls itself unhealthy, with a stopped loop and a lost channel', () => {
    const w = mount(NanoclawCard, {
      props: {
        now,
        nanoclaw: nanoclaw({
          healthy: false,
          message_loop_running: false,
          channels: [
            { name: 'slack', connected: false },
            { name: null, connected: null },
          ],
        }),
      },
    })
    expect(w.find('#nanoclaw-status').text()).toBe('Unhealthy')
    expect(w.find('#nanoclaw-status').attributes('data-status')).toBe('failing')
    expect(w.find('#nanoclaw-loop').text()).toBe('Stopped')
    expect(w.findAll('#nanoclaw-channels li').map((l) => squash(l.text()))).toEqual([
      'slack Not connected',
      'unnamed Unknown',
    ])
  })

  it('says what it does not know rather than leaving a blank', () => {
    const w = mount(NanoclawCard, {
      props: {
        now,
        nanoclaw: nanoclaw({
          healthy: null,
          uptime_seconds: null,
          message_loop_running: null,
          channels: [],
          queue: { active: null, max: null, waiting: null },
          active_session_count: null,
          last_message_at: null,
          tasks: {
            active_count: null,
            paused_count: null,
            next_run_at: null,
            recent_failures: null,
          },
        }),
      },
    })
    expect(w.find('#nanoclaw-status').text()).toBe('Unknown')
    expect(w.find('#nanoclaw-uptime').text()).toBe('Not known')
    expect(w.find('#nanoclaw-channels').text()).toBe('None')
    expect(w.find('#nanoclaw-loop').text()).toBe('Unknown')
    expect(w.find('#nanoclaw-queue').text()).toBe('not known active, not known waiting')
    expect(w.find('#nanoclaw-last-message').text()).toBe('None')
    expect(squash(w.find('#nanoclaw-tasks').text())).toBe('not known active, not known paused')
  })

  it('tells a failed broker read apart from NanoClaw not answering', () => {
    const w = mount(NanoclawCard, {
      props: { now, nanoclaw: { available: false, reason: 'broker_error' } },
    })
    expect(w.find('#nanoclaw-status').text()).toBe('Unknown')
    expect(w.find('#nanoclaw-not-answering').text()).toContain(
      'Couldn’t read NanoClaw’s health through the broker.',
    )
  })
})

describe('the Claude card', () => {
  it('shows a call OneCLI did not inject, a probe with no time and no status', () => {
    const claude = overview().claude
    claude.last_agent_call = { at: NOW, status: null, agent: null, injections_applied: 0 }
    claude.agent_calls_24h = null
    claude.probe = { status: 'unknown', http_status: null, checked_at: null }
    const w = mount(ClaudeCard, { props: { now, claude } })
    expect(squash(w.find('#claude-last-call').text())).toBe(
      'today at 15:30 CET, HTTP unknown (OneCLI did not inject the token)',
    )
    expect(w.find('#claude-agent-calls').text()).toBe('Couldn’t read Loki')
    expect(squash(w.find('#claude-probe').text())).toBe('Unknown')
  })

  it('has no reasons list when there are none', () => {
    const claude = overview().claude
    claude.reasons = []
    expect(mount(ClaudeCard, { props: { now, claude } }).find('#claude-reasons').exists()).toBe(
      false,
    )
  })
})

describe('the quota card', () => {
  const label = overview().quota.label
  const quota = (changes: Partial<Extract<Quota, { available: true }>>): Quota => ({
    available: true,
    label,
    source: 'host ~/.claude login',
    weekly_pct: 39,
    resets_at: null,
    resets_text: null,
    ...changes,
  })

  it('falls back to the reset text, then to saying it is not known', () => {
    const text = mount(QuotaCard, {
      props: { now, quota: quota({ resets_text: 'Nov 10, 9pm (Europe/Amsterdam)' }) },
    })
    expect(text.find('#quota-resets').text()).toBe('Resets Nov 10, 9pm (Europe/Amsterdam)')
    const none = mount(QuotaCard, { props: { now, quota: quota({}) } })
    expect(none.find('#quota-resets').text()).toBe('Reset time not known')
  })

  it('says when the quota text did not parse', () => {
    const w = mount(QuotaCard, { props: { now, quota: quota({ weekly_pct: null }) } })
    expect(w.find('#quota-used').text()).toBe(
      'The quota text didn’t parse, so the share used is not known.',
    )
    expect(w.find('#quota-label').text()).toBe(label)
  })
})

describe('the warning list', () => {
  it('shows an item with no detail, no time and no link', () => {
    const w = mount(WarningList, {
      props: {
        now,
        idPrefix: 'problem',
        items: [
          {
            kind: 'claude_unknown',
            severity: 'info',
            title: 'Claude’s status is unknown',
            detail: null,
            at: null,
            count: null,
            ref: null,
          },
        ],
      },
      global: { stubs },
    })
    expect(w.find('#problem-claude_unknown-0').text()).toContain('Note')
    expect(w.findAll('time')).toHaveLength(0)
    expect(w.findComponent(RouterLinkStub).exists()).toBe(false)
  })
})

describe('the task status', () => {
  it('is plain words for a task that is not paused', () => {
    const w = mount(TaskStatus, {
      props: { task: { ...PAUSED_TASK, status: 'pending', overdue_on_resume: false } },
    })
    expect(w.text()).toBe('Scheduled')
    expect(w.find('[role]').exists()).toBe(false)
  })
})

describe('the page status', () => {
  it('reports a 401 like a 403, and an old answer by its date', () => {
    const w = mount(PageStatus, {
      props: {
        generatedAt: '2026-11-07T10:00:00.000Z',
        checkedAt: now,
        error: { status: 401 },
        sources: null,
      },
    })
    expect(w.find('#page-banner').text()).toContain('The console refused this browser (HTTP 401).')
    const old = mount(PageStatus, {
      props: {
        generatedAt: '2026-11-07T10:00:00.000Z',
        checkedAt: now,
        error: { status: 500 },
        sources: null,
      },
    })
    expect(squash(old.find('#page-banner').text())).toBe(
      'Couldn’t reach the console’s API, so this page shows what it had yesterday at 11:00 CET. It retries every 30 seconds.',
    )
  })
})
