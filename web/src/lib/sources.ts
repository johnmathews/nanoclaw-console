import type { Sources } from './types'

/** What each read is, in words (the broker's verbs and the console's Loki reads, §4.7). */
const READS: Record<string, string> = {
  health: 'NanoClaw’s health',
  usage: 'the quota',
  'claude-probe': 'the Claude probe',
  'tasks-list': 'the task list',
  'tasks-get': 'the task’s details',
  'task-file': 'the task file',
  'groups-list': 'the group list',
  'groups-get': 'the group',
  'groups-config-get': 'a group’s config',
  'approvals-list': 'approvals',
  'dropped-messages-list': 'dropped messages',
  'messaging-groups-list': 'channels',
  'wirings-list': 'wirings',
  'sessions-list': 'sessions',
  'destinations-list': 'destinations',
  'roles-list': 'roles',
  'members-list': 'members',
  'policies-list': 'policies',
  'users-list': 'users',
  'mount-allowlist': 'the mount allowlist',
  claude: 'Claude’s traffic in Loki',
  host_logs: 'NanoClaw’s host logs in Loki',
}

const WHY: Record<string, (source: string) => string> = {
  unavailable: (s) => `${s} did not answer`,
  timeout: (s) => `${s} took too long to answer`,
  not_configured: (s) => `${s} is not configured`,
  protocol_error: (s) => `${s} gave an answer the console could not read`,
  bad_response: (s) => `${s} gave an answer the console could not read`,
  unknown_verb: () => 'this broker does not offer that read',
  invalid_params: () => 'the broker refused the request',
  ncl_error: () => 'NanoClaw refused the request',
}

export type SourceProblem = { what: string; why: string; code: string }

/** Each failed read, broker first, in words, with its code. */
export function sourceProblems(sources: Sources): SourceProblem[] {
  const out: SourceProblem[] = []
  for (const [source, state] of [
    ['the broker', sources.broker],
    ['Loki', sources.loki],
  ] as const) {
    for (const [read, code] of Object.entries(state?.errors ?? {})) {
      const why = WHY[code]
      out.push({ what: READS[read] ?? read, why: why ? why(source) : 'it failed', code })
    }
  }
  return out
}
