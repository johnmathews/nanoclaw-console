import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GROUP_IDS, groupsView, UNWIRED_CHANNEL_ID } from '../../fixtures/api'
import { mountApp, text, useClock } from '../../__tests__/mountApp'
import type { GroupsView } from '../../lib/types'

async function open(body: unknown = groupsView(), path = '/groups') {
  return mountApp(path, { '/api/groups': body })
}

const MAIN = GROUP_IDS.main
const SERVER = GROUP_IDS.server
const INTRO = GROUP_IDS.introspection

describe('the groups page', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('answers first: how many groups and channels, and what stands out', async () => {
    const wrapper = await open()
    expect(text(wrapper, 'h1')).toBe('Groups and channels')
    expect(document.title).toBe('Groups and channels · NanoClaw console')
    expect(text(wrapper, '#groups-answer')).toBe(
      'Three groups and five channels. Two channels are wired to no group. Two groups can write to files on the host.',
    )
  })

  it('draws a card per group, linked to the group’s page', async () => {
    const wrapper = await open()
    expect(wrapper.findAll('#groups-list > li')).toHaveLength(3)
    const link = wrapper.find(`#group-card-${MAIN} h3 a`)
    expect(link.text()).toBe('main-group')
    expect(link.attributes('href')).toBe(`/groups/${MAIN}`)
  })

  it('gives each group’s model and provider, channels, MCP servers, mounts and tasks', async () => {
    const wrapper = await open()
    expect(text(wrapper, `#group-${MAIN}-model`)).toBe('claude-opus-4-7, provider not set')
    expect(text(wrapper, `#group-${SERVER}-model`)).toBe('claude-sonnet-4-6, provider anthropic')
    expect(wrapper.findAll(`#group-${MAIN}-channels li`).map((li) => li.text())).toEqual([
      'John (DM): every message',
      'Terminal: when it is mentioned',
    ])
    expect(text(wrapper, `#group-${INTRO}-channels`)).toBe('None wired')
    expect(text(wrapper, `#group-${MAIN}-mcp`)).toBe('journal, parallel-search, files')
    expect(text(wrapper, `#group-${SERVER}-mcp`)).toBe('None')
    expect(text(wrapper, `#group-${MAIN}-mounts`)).toBe('2 mounts, 1 read-write')
    expect(text(wrapper, `#group-${SERVER}-mounts`)).toBe('1 mount, read-only')
    expect(text(wrapper, `#group-${MAIN}-tasks`)).toBe(
      '3 tasks, 2 paused (each would run once straight away if resumed)',
    )
    expect(text(wrapper, `#group-${INTRO}-tasks`)).toBe('None')
    expect(text(wrapper, `#group-${MAIN}-sessions`)).toBe('6, 1 running')
  })

  it('flags a group that can write to the host as a caution, in words', async () => {
    const wrapper = await open()
    const rw = wrapper.find(`#group-${INTRO}-mounts [role="status"]`)
    expect(rw.exists()).toBe(true)
    expect(rw.classes()).toContain('text-caution-ink')
    expect(wrapper.find(`#group-${SERVER}-mounts [role="status"]`).exists()).toBe(false)
  })

  it('says when a group’s config could not be read', async () => {
    const body = groupsView()
    body.groups[1]!.config = null
    body.sources = { broker: { ok: false, errors: { 'groups-config-get': 'timeout' } } }
    const wrapper = await open(body)
    expect(text(wrapper, `#group-${SERVER}-model`)).toBe('Couldn’t read')
    expect(text(wrapper, `#group-${SERVER}-mcp`)).toBe('Couldn’t read')
    expect(text(wrapper, `#group-${SERVER}-mounts`)).toBe('Couldn’t read')
    expect(text(wrapper, '#page-sources')).toContain('Couldn’t read a group’s config')
  })

  it('lists the channels wired to no group, with their sender policy', async () => {
    const wrapper = await open()
    const items = wrapper.findAll('#unwired-channels li')
    expect(items).toHaveLength(2)
    expect(text(wrapper, `#channel-${UNWIRED_CHANNEL_ID}`)).toContain('#random')
    expect(text(wrapper, `#channel-${UNWIRED_CHANNEL_ID}-unknown`)).toBe(
      'Allowed: anyone may message it public',
    )
    expect(text(wrapper, '#channel-mg-1780200000000-dn1ed0')).toContain('whatsapp:31600000000')
    expect(text(wrapper, '#channel-mg-1780200000000-dn1ed0')).toContain(
      'Denied 2 June at 20:30 CEST',
    )
  })

  it('anchors a wired channel once, on the first group that has it', async () => {
    const body = groupsView()
    body.groups[1]!.channels.push({ ...body.groups[0]!.channels[0]! })
    const wrapper = await open(body)
    expect(wrapper.findAll('#channel-mg-1779373702900-slkdm1')).toHaveLength(1)
    expect(wrapper.find(`#group-card-${MAIN} #channel-mg-1779373702900-slkdm1`).exists()).toBe(true)
  })

  it('says when there are no unwired channels, and when there are no groups', async () => {
    const body: GroupsView = { ...groupsView(), unwired_channels: [] }
    const wrapper = await open(body)
    expect(text(wrapper, '#unwired-channels')).toContain('Every channel is wired to a group.')
    wrapper.unmount()
    document.body.innerHTML = ''
    const empty = await open({ ...groupsView(), groups: [], unwired_channels: [] })
    expect(text(empty, '#groups-answer')).toBe('No groups.')
    expect(empty.find('#groups-list').exists()).toBe(false)
  })
})

describe('a group’s page', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('names the group, with its folder and id, under a link back', async () => {
    const wrapper = await open(groupsView(), `/groups/${MAIN}`)
    expect(text(wrapper, 'h1')).toBe('main-group')
    expect(document.title).toBe('main-group · NanoClaw console')
    expect(wrapper.find('#group-back').attributes('href')).toBe('/groups')
    expect(text(wrapper, '#group-ids')).toBe(`main ${MAIN}`)
  })

  it('gives the model, provider and the rest of the config', async () => {
    const wrapper = await open(groupsView(), `/groups/${MAIN}`)
    expect(text(wrapper, '#group-model')).toBe('claude-opus-4-7')
    expect(text(wrapper, '#group-provider')).toBe('Not set (NanoClaw’s default)')
    expect(text(wrapper, '#group-effort')).toBe('high')
    expect(text(wrapper, '#group-packages')).toBe('apt: ripgrep')
    expect(text(wrapper, '#group-tasks')).toContain('3 tasks, 2 paused')
  })

  it('shows each wired channel’s engage mode, pattern, sender scope and unknown-sender policy', async () => {
    const wrapper = await open(groupsView(), `/groups/${MAIN}`)
    const dm = '#group-channel-mga-1779373703000-w1main'
    expect(text(wrapper, `${dm} h3`)).toBe('John (DM)')
    expect(text(wrapper, `${dm}-engage`)).toBe('Every message (pattern .)')
    expect(text(wrapper, `${dm}-senders`)).toBe('Anyone in the channel all')
    expect(text(wrapper, `${dm}-unknown`)).toBe('Dropped without a reply strict')
    const cli = '#group-channel-mga-1779373703001-w2cli'
    expect(text(wrapper, `${cli}-engage`)).toBe('When it is mentioned mention')
    expect(text(wrapper, `${cli}-senders`)).toBe('Known users only (members, admins, owners) known')
    expect(text(wrapper, `${cli}-ignored`)).toBe('Kept as context accumulate')
    expect(text(wrapper, `${cli}-sessions`)).toBe('One session per thread per-thread')
  })

  it('shows MCP servers by name and host only, with header and env names but no values', async () => {
    const wrapper = await open(groupsView(), `/groups/${MAIN}`)
    expect(wrapper.findAll('#group-mcp li')).toHaveLength(3)
    expect(text(wrapper, '#mcp-journal')).toContain('journal')
    expect(text(wrapper, '#mcp-journal-where')).toBe('journal.example.internal:8443')
    expect(text(wrapper, '#mcp-journal')).not.toContain('https://')
    expect(text(wrapper, '#mcp-journal-secrets')).toBe(
      'Sends header Authorization; its value is not shown',
    )
    expect(text(wrapper, '#mcp-files-where')).toBe('/usr/local/bin/mcp-files')
    expect(text(wrapper, '#mcp-files-secrets')).toBe(
      'Sets env FILES_TOKEN and passes 2 arguments; their values are not shown',
    )
    expect(text(wrapper, '#mcp-parallel-search-secrets')).toBe(
      'Sends headers Authorization, X-Client; their values are not shown',
    )
  })

  it('flags read-write mounts clearly and read-only ones plainly', async () => {
    const wrapper = await open(groupsView(), `/groups/${MAIN}`)
    const mounts = wrapper.findAll('#group-mounts li')
    expect(mounts).toHaveLength(2)
    expect(mounts[0]!.attributes('data-access')).toBe('read-only')
    expect(mounts[1]!.attributes('data-access')).toBe('read-write')
    expect(text(wrapper, '#mount-1')).toContain('Read-write: the agent can change these files')
    expect(text(wrapper, '#mount-0')).toContain('Read-only')
    expect(text(wrapper, '#mount-1')).toContain(
      '/workspace/extra/scratch from /srv/apps/nanoclaw/groups/main/scratch',
    )
  })

  it('says whom the group may message', async () => {
    const wrapper = await open(groupsView(), `/groups/${MAIN}`)
    expect(wrapper.findAll('#group-destinations li')).toHaveLength(2)
    expect(text(wrapper, '#destination-0')).toBe('server → #server (a slack channel)')
    expect(text(wrapper, '#destination-1')).toBe('server-bot → server-bot (an agent)')
  })

  it('says none for a group with no channels, servers, mounts or destinations', async () => {
    const body = groupsView()
    body.groups[2]!.config!.mounts = []
    const wrapper = await open(body, `/groups/${INTRO}`)
    expect(text(wrapper, '#group-channels')).toContain('No channel is wired to this group')
    expect(text(wrapper, '#group-mcp')).toContain('No MCP servers.')
    expect(text(wrapper, '#group-mounts')).toContain('No extra mounts.')
    expect(text(wrapper, '#group-destinations')).toContain('No destinations.')
  })

  it('says when the group’s config could not be read', async () => {
    const body = groupsView()
    body.groups[0]!.config = null
    const wrapper = await open(body, `/groups/${MAIN}`)
    expect(text(wrapper, '#group-config-failed')).toContain('Couldn’t read this group’s config')
    expect(wrapper.find('#group-mcp li').exists()).toBe(false)
  })

  it('says when there is no such group, and when the list could not be read', async () => {
    const wrapper = await open(groupsView(), '/groups/ag-nope')
    expect(text(wrapper, 'h1')).toBe('Group not found')
    expect(text(wrapper, '#group-missing')).toContain('There is no group ag-nope.')
    wrapper.unmount()
    document.body.innerHTML = ''
    const failed = await open(
      {
        ...groupsView(),
        groups: [],
        sources: { broker: { ok: false, errors: { 'groups-list': 'unavailable' } } },
      },
      '/groups/ag-nope',
    )
    expect(text(failed, '#group-missing')).toBe(
      'Couldn’t read the group list, so this group can’t be shown. It retries every 30 seconds.',
    )
  })
})
