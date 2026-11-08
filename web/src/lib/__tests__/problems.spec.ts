import { describe, expect, it } from 'vitest'
import { problemsView, STALE_APPROVAL_ID } from '../../fixtures/api'
import { problemsAnswer, refLink } from '../problems'
import type { ProblemItem } from '../types'

describe('the problems page’s answer line', () => {
  it('counts by severity, in words', () => {
    expect(problemsAnswer(problemsView().items)).toBe(
      'One error, six warnings and one note need a look.',
    )
  })

  it('words one of a kind, and none', () => {
    const one = problemsView().items.slice(0, 1)
    expect(problemsAnswer(one)).toBe('One error needs a look.')
    expect(problemsAnswer([])).toBe('Nothing needs a look.')
    const two = problemsView()
      .items.filter((i) => i.severity !== 'error')
      .slice(0, 2)
    expect(problemsAnswer(two)).toBe('Two warnings need a look.')
  })
})

describe('where a problem links', () => {
  const ref = (type: NonNullable<ProblemItem['ref']>['type'], id: string) => ({ type, id })

  it('links a task to its page, a group to its page and an approval to its row', () => {
    expect(refLink(ref('task', 'task-1'))).toEqual({ to: '/tasks/task-1', label: 'Open the task' })
    expect(refLink(ref('group', 'ag-1'))).toEqual({ to: '/groups/ag-1', label: 'Open the group' })
    expect(refLink(ref('approval', STALE_APPROVAL_ID))).toEqual({
      to: `/permissions#approval-${STALE_APPROVAL_ID}`,
      label: 'See the approval',
    })
  })

  it('sends a channel to the groups page and a source nowhere', () => {
    expect(refLink(ref('channel', 'mg-1'))).toEqual({
      to: '/groups#channel-mg-1',
      label: 'See groups and channels',
    })
    expect(refLink(ref('source', 'broker'))).toBeNull()
    expect(refLink(null)).toBeNull()
  })

  it('encodes an id that is not a plain word', () => {
    expect(refLink(ref('task', 'a b'))?.to).toBe('/tasks/a%20b')
  })
})
