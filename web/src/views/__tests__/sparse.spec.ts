// The W9 pages with the API's sparse answers: every nullable field null, empty lists beside
// failed reads, and the singulars. Each must say "Not known", "None" or "Couldn’t read" in
// words, never leave a blank (voice.md).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GROUP_IDS, groupsView, permissionsView, problemsView } from '../../fixtures/api'
import { mountApp, text, useClock } from '../../__tests__/mountApp'
import type { Channel, Group } from '../../lib/types'

const bareChannel: Channel = {
  wiring_id: null,
  messaging_group_id: null,
  name: null,
  channel_type: null,
  instance: null,
  platform_id: null,
  is_group: null,
  engage_mode: null,
  engage_pattern: null,
  sender_scope: null,
  ignored_message_policy: null,
  unknown_sender_policy: null,
  session_mode: null,
  priority: null,
  threads: null,
  denied_at: '2026-11-01T09:00:00.000Z',
}

function bareGroup(): Group {
  return {
    id: 'ag-bare',
    name: null,
    folder: null,
    created_at: null,
    config: {
      model: null,
      provider: null,
      effort: null,
      speed: null,
      assistant_name: null,
      cli_scope: null,
      timezone: null,
      image_tag: null,
      max_messages_per_prompt: null,
      skills: null,
      packages_apt: [],
      packages_npm: ['tsx'],
      updated_at: null,
      mcp_servers: [
        {
          name: 'odd name',
          type: null,
          transport: null,
          url: null,
          command: null,
          header_names: [],
          env_names: ['ONE'],
          arg_count: 1,
        },
        {
          name: 'quiet',
          type: 'stdio',
          transport: null,
          url: null,
          command: null,
          header_names: [],
          env_names: [],
          arg_count: 0,
        },
        {
          name: 'one-arg',
          type: 'stdio',
          transport: null,
          url: null,
          command: '/bin/x',
          header_names: [],
          env_names: [],
          arg_count: 1,
        },
      ],
      mounts: [{ host_path: null, container_path: null, read_only: true }],
    },
    channels: [
      bareChannel,
      { ...bareChannel, engage_mode: 'pattern', engage_pattern: null, denied_at: null },
    ],
    destinations: [
      {
        local_name: null,
        display_name: null,
        channel_type: null,
        target_type: 'channel',
        target_id: null,
        target_name: null,
        created_at: null,
      },
      {
        local_name: 'x',
        display_name: null,
        channel_type: null,
        target_type: null,
        target_id: 'ag-x',
        target_name: null,
        created_at: null,
      },
    ],
    sessions: { total: 1, running: 0 },
    tasks: { total: 1, paused: 1, overdue_on_resume: 1 },
  }
}

describe('sparse answers', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('the groups page words every null and singular', async () => {
    const body = groupsView()
    const two = {
      ...bareGroup(),
      id: 'ag-two',
      tasks: { total: 3, paused: 2, overdue_on_resume: 1 },
    }
    const three = {
      ...bareGroup(),
      id: 'ag-three',
      tasks: { total: 2, paused: 1, overdue_on_resume: 0 },
    }
    body.groups = [bareGroup(), two, three]
    body.unwired_channels = [
      {
        id: null,
        name: null,
        channel_type: null,
        instance: null,
        platform_id: null,
        unknown_sender_policy: null,
        denied_at: null,
      },
    ]
    const wrapper = await mountApp('/groups', { '/api/groups': body })
    expect(text(wrapper, '#group-card-ag-bare h3')).toBe('ag-bare')
    expect(text(wrapper, '#group-ag-bare-model')).toBe('Model not set, provider not set')
    expect(text(wrapper, '#group-ag-bare-tasks')).toBe(
      '1 task, 1 paused (would run once straight away if resumed)',
    )
    expect(text(wrapper, '#group-ag-two-tasks')).toBe(
      '3 tasks, 2 paused (1 would run once straight away if resumed)',
    )
    expect(text(wrapper, '#group-ag-three-tasks')).toBe('2 tasks, 1 paused')
    expect(text(wrapper, '#group-ag-bare-channels')).toContain('Unnamed channel: not known')
    expect(text(wrapper, '#unwired-0')).toContain('Unnamed channel unknown type')
    expect(text(wrapper, '#unwired-0')).toContain('Not known')
  })

  it('the groups page does not claim every channel is wired when channels could not be read', async () => {
    const body = groupsView()
    body.unwired_channels = []
    body.sources = { broker: { ok: false, errors: { 'messaging-groups-list': 'timeout' } } }
    const wrapper = await mountApp('/groups', { '/api/groups': body })
    expect(text(wrapper, '#unwired-channels')).toContain('Couldn’t read the channels.')
  })

  it('a group’s page words every null', async () => {
    const body = groupsView()
    body.groups = [bareGroup()]
    const wrapper = await mountApp('/groups/ag-bare', { '/api/groups': body })
    expect(text(wrapper, 'h1')).toBe('ag-bare')
    expect(text(wrapper, '#group-ids')).toBe('ag-bare')
    expect(text(wrapper, '#group-model')).toBe('Not set (NanoClaw’s default)')
    expect(text(wrapper, '#group-effort')).toBe('Not set')
    expect(text(wrapper, '#group-packages')).toBe('npm: tsx')
    expect(text(wrapper, '#group-config-updated')).toBe('Not known')
    expect(text(wrapper, '#group-created')).toBe('Not known')
    expect(text(wrapper, '#group-tasks')).toContain('1 task, 1 paused')
    const ch = '#group-channel-0'
    expect(text(wrapper, `${ch} h3`)).toBe('Unnamed channel')
    expect(text(wrapper, ch)).toContain('Unknown type · no platform id')
    expect(text(wrapper, `${ch}-engage`)).toBe('Not known')
    expect(text(wrapper, `${ch}-senders`)).toBe('Not set')
    expect(text(wrapper, ch)).toContain('The channel was denied 1 November at 10:00 CET.')
    expect(text(wrapper, '#group-channel-1-engage')).toBe(
      'Messages that match a pattern (none is set) pattern',
    )
    expect(text(wrapper, '#mcp-odd-name')).toContain('type not known')
    expect(text(wrapper, '#mcp-odd-name-where')).toBe('Not known')
    expect(text(wrapper, '#mcp-odd-name-secrets')).toBe(
      'Sets env ONE and passes 1 argument; their values are not shown',
    )
    expect(wrapper.find('#mcp-quiet-secrets').exists()).toBe(false)
    expect(text(wrapper, '#mcp-one-arg-secrets')).toBe('Passes 1 argument; its value is not shown')
    expect(text(wrapper, '#mount-0')).toContain('Not known from Not known')
    expect(text(wrapper, '#destination-0')).toBe('unnamed → an unknown target (a channel)')
    expect(text(wrapper, '#destination-1')).toBe('x → ag-x (unknown kind)')
  })

  it('a group’s page waits quietly before the first answer', async () => {
    const wrapper = await mountApp(`/groups/${GROUP_IDS.main}`, { '/api/groups': 503 })
    expect(text(wrapper, 'h1')).toBe('Group')
    expect(text(wrapper, '#page-banner')).toContain('Couldn’t reach the console’s API')
  })

  it('the permissions page words every null, failed read and singular', async () => {
    const body = permissionsView()
    body.roles = [
      { ...body.roles[1]!, granted_at: null, role: 'admin', scope: 'group', group: null },
    ]
    body.members = [{ ...body.members[0]!, user_kind: null, added_at: null, added_by: 'someone' }]
    body.policies = [{}, {}]
    body.destinations = []
    body.approvals = [
      {
        id: null,
        action: null,
        title: null,
        status: null,
        created_at: null,
        expires_at: '2026-11-01T00:00:00.000Z',
        age_days: 9,
        stale: true,
        group: null,
        session_id: null,
      },
    ]
    body.mount_allowlist = {
      available: true,
      allowed_roots: [],
      blocked_patterns: [],
      non_main_read_only: false,
    }
    body.sources = { broker: { ok: false, errors: { 'destinations-list': 'timeout' } } }
    const wrapper = await mountApp('/permissions', { '/api/permissions': body })
    expect(text(wrapper, '#permissions-answer')).toBe(
      'One admin. One group membership. One approval has waited more than a week.',
    )
    expect(text(wrapper, '#role-0')).toContain('Admin, everywhere')
    expect(text(wrapper, '#role-0')).toContain('Granted at a time not known')
    expect(text(wrapper, '#member-0')).toContain('by someone')
    expect(text(wrapper, '#policies-summary')).toBe(
      'Two policies. The console doesn’t show their fields yet; ncl policies list does.',
    )
    expect(text(wrapper, '#destinations')).toContain('Couldn’t read the destinations.')
    expect(text(wrapper, '#approval-0')).toContain('Untitled')
    expect(text(wrapper, '#approval-0')).toContain('Status not known · unknown action')
    expect(text(wrapper, '#approval-0')).toContain('Waiting 9 days.')
    expect(text(wrapper, '#mount-allowlist')).toContain('No roots: no group may mount anything.')
    expect(text(wrapper, '#mount-allowlist')).toContain('nothing listed')
    expect(text(wrapper, '#non-main-read-only')).toBe(
      'Groups other than main may get read-write mounts where a root allows it.',
    )
  })

  it('the permissions page says when policies, approvals and the allowlist rule could not be read', async () => {
    const body = permissionsView()
    body.policies = []
    body.approvals = []
    body.mount_allowlist = {
      available: true,
      allowed_roots: [],
      blocked_patterns: [],
      non_main_read_only: null,
    }
    body.sources = {
      broker: { ok: false, errors: { 'policies-list': 'timeout', 'approvals-list': 'timeout' } },
    }
    const wrapper = await mountApp('/permissions', { '/api/permissions': body })
    expect(text(wrapper, '#policies-summary')).toBe('Couldn’t read the policies.')
    expect(text(wrapper, '#approvals')).toContain('Couldn’t read the approvals.')
    expect(text(wrapper, '#non-main-read-only')).toBe(
      'Whether other groups get read-only mounts is not set.',
    )
  })

  it('the problems page words one error, one warning and a FATAL line', async () => {
    const body = problemsView()
    body.host_logs = {
      window_hours: 24,
      errors: 1,
      warnings: 1,
      truncated: false,
      groups: [{ ...body.host_logs!.groups[0]!, level: 'FATAL', count: 1 }],
    }
    const wrapper = await mountApp('/problems', { '/api/problems': body })
    expect(text(wrapper, '#host-logs-summary')).toBe(
      '1 error and 1 warning in the last 24 hours, in one group by message.',
    )
    expect(text(wrapper, '#log-group-0-count')).toBe('1 time')
    expect(text(wrapper, '#log-group-0')).toContain('Error')
  })
})
