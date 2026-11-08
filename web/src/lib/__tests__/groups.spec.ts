import { describe, expect, it } from 'vitest'
import { groupsView } from '../../fixtures/api'
import {
  channelLabel,
  domId,
  engageWords,
  groupName,
  groupsAnswer,
  mcpWhere,
  mountSummary,
  policyWords,
} from '../groups'
import type { Channel, GroupsView, McpServer } from '../types'

const channel = (over: Partial<Channel>): Channel => ({
  ...groupsView().groups[0]!.channels[0]!,
  ...over,
})

describe('a channel’s policies in words', () => {
  it('says when the agent engages', () => {
    expect(engageWords(channel({ engage_mode: 'pattern', engage_pattern: '.' }))).toBe(
      'Every message',
    )
    expect(engageWords(channel({ engage_mode: 'pattern', engage_pattern: '^claw' }))).toBe(
      'Messages that match a pattern',
    )
    expect(engageWords(channel({ engage_mode: 'pattern', engage_pattern: null }))).toBe(
      'Messages that match a pattern (none is set)',
    )
    expect(engageWords(channel({ engage_mode: 'mention' }))).toBe('When it is mentioned')
    expect(engageWords(channel({ engage_mode: 'mention-sticky' }))).toBe(
      'When it is mentioned, then the rest of that thread',
    )
    expect(engageWords(channel({ engage_mode: 'some_new_mode' }))).toBe('Some new mode')
    expect(engageWords(channel({ engage_mode: null }))).toBe('Not known')
  })

  it('says who may engage, what happens to unknown senders and to other messages', () => {
    expect(policyWords('sender_scope', 'all')).toBe('Anyone in the channel')
    expect(policyWords('sender_scope', 'known')).toBe('Known users only (members, admins, owners)')
    expect(policyWords('unknown_sender_policy', 'strict')).toBe('Dropped without a reply')
    expect(policyWords('unknown_sender_policy', 'request_approval')).toBe(
      'An admin is asked to approve them',
    )
    expect(policyWords('unknown_sender_policy', 'public')).toBe('Allowed: anyone may message it')
    expect(policyWords('unknown_sender_policy', 'decline_notify')).toBe('Decline notify')
    expect(policyWords('ignored_message_policy', 'drop')).toBe('Dropped')
    expect(policyWords('ignored_message_policy', 'accumulate')).toBe('Kept as context')
    expect(policyWords('session_mode', 'shared')).toBe('One session for the channel')
    expect(policyWords('session_mode', 'per-thread')).toBe('One session per thread')
    expect(policyWords('session_mode', 'agent-shared')).toBe(
      'One session across all the group’s channels',
    )
    expect(policyWords('session_mode', null)).toBe('Not set')
  })

  it('names a channel by its name, else its platform id, else its id', () => {
    expect(
      channelLabel({ name: '#server', platform_id: 'slack:C1', messaging_group_id: 'mg-1' }),
    ).toBe('#server')
    expect(channelLabel({ name: null, platform_id: 'slack:C1', id: 'mg-1' })).toBe('slack:C1')
    expect(channelLabel({ name: null, platform_id: null, id: 'mg-1' })).toBe('mg-1')
    expect(channelLabel({ name: null, platform_id: null, messaging_group_id: null })).toBe(
      'Unnamed channel',
    )
  })
})

describe('MCP servers and mounts', () => {
  const server = (over: Partial<McpServer>): McpServer => ({
    name: 'x',
    type: 'http',
    transport: null,
    url: null,
    command: null,
    header_names: [],
    env_names: [],
    arg_count: 0,
    ...over,
  })

  it('shows only the host of a server’s address, or the command it runs', () => {
    expect(mcpWhere(server({ url: 'https://journal.example.internal:8443' }))).toEqual({
      label: 'Host',
      value: 'journal.example.internal:8443',
    })
    expect(mcpWhere(server({ url: 'not a url' }))).toEqual({ label: 'Host', value: 'not a url' })
    expect(mcpWhere(server({ command: '/usr/local/bin/mcp-files' }))).toEqual({
      label: 'Runs',
      value: '/usr/local/bin/mcp-files',
    })
    expect(mcpWhere(server({}))).toEqual({ label: 'Host', value: null })
  })

  it('counts mounts and says how many are read-write', () => {
    const mounts = groupsView().groups[0]!.config!.mounts
    expect(mountSummary(mounts)).toBe('2 mounts, 1 read-write')
    expect(mountSummary([mounts[0]!])).toBe('1 mount, read-only')
    expect(mountSummary([mounts[1]!])).toBe('1 mount, read-write')
    expect(mountSummary([mounts[0]!, mounts[0]!])).toBe('2 mounts, all read-only')
    expect(mountSummary([])).toBe('None')
  })
})

describe('the groups page’s answer line', () => {
  it('counts groups and channels, and names the unwired and read-write ones', () => {
    expect(groupsAnswer(groupsView())).toBe(
      'Three groups and five channels. Two channels are wired to no group. Two groups can write to files on the host.',
    )
  })

  it('handles one of each, and none', () => {
    const one = groupsView()
    one.groups = [one.groups[1]!]
    one.unwired_channels = [one.unwired_channels[0]!]
    expect(groupsAnswer(one)).toBe('One group and two channels. One channel is wired to no group.')
    const none: GroupsView = { ...groupsView(), groups: [], unwired_channels: [] }
    expect(groupsAnswer(none)).toBe('No groups.')
  })

  it('does not claim none when the list could not be read', () => {
    const failed: GroupsView = {
      ...groupsView(),
      groups: [],
      unwired_channels: [],
      sources: { broker: { ok: false, errors: { 'groups-list': 'unavailable' } } },
    }
    expect(groupsAnswer(failed)).toBe('Couldn’t read the group list.')
  })

  it('counts a channel wired to two groups once', () => {
    const v = groupsView()
    v.groups[1]!.channels.push({ ...v.groups[0]!.channels[0]! })
    expect(groupsAnswer(v)).toContain('Three groups and five channels.')
  })
})

describe('names and ids', () => {
  it('names a group by name, else folder, else id', () => {
    expect(groupName({ id: 'ag-1', name: 'main', folder: 'm' })).toBe('main')
    expect(groupName({ id: 'ag-1', name: null, folder: 'm' })).toBe('m')
    expect(groupName({ id: 'ag-1', name: null })).toBe('ag-1')
  })

  it('makes a safe DOM id from anything', () => {
    expect(domId('parallel-search')).toBe('parallel-search')
    expect(domId('slack:U07 x/y')).toBe('slack-U07-x-y')
  })
})
