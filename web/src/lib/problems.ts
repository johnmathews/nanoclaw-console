import type { ProblemItem } from './types'
import { domId } from './groups'
import { countWords, listWords } from './words'

/** "One error, six warnings and one note need a look." */
export function problemsAnswer(items: ProblemItem[]): string {
  if (!items.length) return 'Nothing needs a look.'
  const count = (s: ProblemItem['severity']) => items.filter((i) => i.severity === s).length
  const said = (
    [
      [count('error'), 'error'],
      [count('warning'), 'warning'],
      [count('info'), 'note'],
    ] as const
  )
    .filter(([n]) => n)
    .map(([n, word], i) => {
      const s = countWords(n, word)
      return i ? s.toLowerCase() : s
    })
  return `${listWords(said)} ${items.length === 1 ? 'needs' : 'need'} a look.`
}

/**
 * Where a problem's `ref` leads: a task or group to its page, an approval to its row on the
 * permissions page, a channel to the groups page (anchored on the channel when it is drawn
 * there). A source has no page: PageStatus already names the failed reads.
 */
export function refLink(ref: ProblemItem['ref']): { to: string; label: string } | null {
  if (!ref) return null
  const id = encodeURIComponent(ref.id)
  switch (ref.type) {
    case 'task':
      return { to: `/tasks/${id}`, label: 'Open the task' }
    case 'group':
      return { to: `/groups/${id}`, label: 'Open the group' }
    case 'approval':
      return { to: `/permissions#approval-${domId(ref.id)}`, label: 'See the approval' }
    case 'channel':
      return { to: `/groups#channel-${domId(ref.id)}`, label: 'See groups and channels' }
    default:
      return null
  }
}
