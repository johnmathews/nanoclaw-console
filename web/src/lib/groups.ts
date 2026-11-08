import type { Channel, GroupsView, McpServer, Mount } from './types'
import { countWords, humanise } from './words'

/** A group's name, else its folder, else its id. */
export function groupName(group: { id: string; name: string | null; folder?: string | null }) {
  return group.name ?? group.folder ?? group.id
}

/** A channel's name, else its platform id, else its messaging group id. */
export function channelLabel(c: {
  name: string | null
  platform_id: string | null
  id?: string | null
  messaging_group_id?: string | null
}): string {
  return c.name ?? c.platform_id ?? c.id ?? c.messaging_group_id ?? 'Unnamed channel'
}

/** A string any id can be turned into for a DOM id: letters, digits, `-` and `_` only. */
export function domId(raw: string): string {
  return raw.replace(/[^A-Za-z0-9_-]/g, '-')
}

/**
 * When the agent engages (NanoClaw's `engage_mode`, docs/db-central.md §1.3): a pattern of `.`
 * matches every message.
 */
export function engageWords(c: Pick<Channel, 'engage_mode' | 'engage_pattern'>): string {
  switch (c.engage_mode) {
    case null:
      return 'Not known'
    case 'pattern':
      if (c.engage_pattern === '.') return 'Every message'
      return c.engage_pattern
        ? 'Messages that match a pattern'
        : 'Messages that match a pattern (none is set)'
    case 'mention':
      return 'When it is mentioned'
    case 'mention-sticky':
      return 'When it is mentioned, then the rest of that thread'
    default:
      return humanise(c.engage_mode)
  }
}

const POLICIES = {
  sender_scope: {
    all: 'Anyone in the channel',
    known: 'Known users only (members, admins, owners)',
  },
  unknown_sender_policy: {
    strict: 'Dropped without a reply',
    request_approval: 'An admin is asked to approve them',
    public: 'Allowed: anyone may message it',
  },
  ignored_message_policy: {
    drop: 'Dropped',
    accumulate: 'Kept as context',
  },
  session_mode: {
    shared: 'One session for the channel',
    'per-thread': 'One session per thread',
    'agent-shared': 'One session across all the group’s channels',
  },
} as const satisfies Record<string, Record<string, string>>

export type PolicyAxis = keyof typeof POLICIES

/** A wiring or channel policy in words; a value the console doesn't know is shown as its words. */
export function policyWords(axis: PolicyAxis, value: string | null): string {
  if (value === null) return 'Not set'
  return (POLICIES[axis] as Record<string, string>)[value] ?? humanise(value)
}

/** Where an MCP server is: the host of its (already reduced) URL, or the command it runs. */
export function mcpWhere(s: McpServer): { label: 'Host' | 'Runs'; value: string | null } {
  if (s.url) {
    try {
      return { label: 'Host', value: new URL(s.url).host || s.url }
    } catch {
      return { label: 'Host', value: s.url }
    }
  }
  if (s.command) return { label: 'Runs', value: s.command }
  return { label: 'Host', value: null }
}

/** "2 mounts, 1 read-write" — figures, since it sits in a card's facts. */
export function mountSummary(mounts: Mount[]): string {
  if (!mounts.length) return 'None'
  const rw = mounts.filter((m) => !m.read_only).length
  const n = `${mounts.length} ${mounts.length === 1 ? 'mount' : 'mounts'}`
  if (mounts.length === 1) return `${n}, ${rw ? 'read-write' : 'read-only'}`
  return `${n}, ${rw ? `${rw} read-write` : 'all read-only'}`
}

/** The groups page's answer line. */
export function groupsAnswer(view: GroupsView): string {
  if (!view.groups.length)
    return 'groups-list' in view.sources.broker.errors
      ? 'Couldn’t read the group list.'
      : 'No groups.'
  const wired = new Set<string>()
  for (const g of view.groups)
    for (const c of g.channels) wired.add(c.messaging_group_id ?? c.wiring_id ?? '')
  const channels = wired.size + view.unwired_channels.length
  const parts = [
    `${countWords(view.groups.length, 'group')} and ${countWords(channels, 'channel').toLowerCase()}.`,
  ]
  const unwired = view.unwired_channels.length
  if (unwired)
    parts.push(
      `${countWords(unwired, 'channel')} ${unwired === 1 ? 'is' : 'are'} wired to no group.`,
    )
  const writers = view.groups.filter((g) => g.config?.mounts.some((m) => !m.read_only)).length
  if (writers) parts.push(`${countWords(writers, 'group')} can write to files on the host.`)
  return parts.join(' ')
}
