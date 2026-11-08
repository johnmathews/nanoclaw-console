import type { ClaudeStatus, NanoclawHealth } from './types'

const CLAUDE: Record<ClaudeStatus, string> = {
  ok: 'Claude is answering NanoClaw’s agents.',
  degraded: 'Claude is answering, with problems.',
  failing: 'Claude is refusing NanoClaw’s token.',
  unknown: 'The console can’t tell whether Claude is answering.',
}

export function claudeSentence(status: ClaudeStatus): string {
  return CLAUDE[status]
}

export function nanoclawSentence(n: NanoclawHealth): string {
  if (!n.available)
    return n.reason === 'not_answering'
      ? 'NanoClaw is not answering.'
      : 'The console couldn’t read NanoClaw’s health.'
  if (n.healthy === false) return 'NanoClaw is running, but says it is unhealthy.'
  return 'NanoClaw is running.'
}
