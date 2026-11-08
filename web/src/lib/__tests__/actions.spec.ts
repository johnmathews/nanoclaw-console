import { describe, expect, it } from 'vitest'
import {
  auditActionWords,
  auditAnswer,
  auditResultWords,
  auditTargetPath,
  groupConfirmation,
  outcomeWords,
  taskActions,
  taskConfirmation,
  type ActionName,
} from '../actions'
import { auditView, groupsView, NOW, PAUSED_TASK, TASKS } from '../../fixtures/api'
import { taskName } from '../tasks'
import type { AuditEntry, Task } from '../types'

const now = new Date(NOW)
const PENDING = TASKS[0]! // inbox-check, scheduled
const MAIN = groupsView().groups[0]!
const IDLE = groupsView().groups[2]!

function task(over: Partial<Task>): Task {
  return { ...structuredClone(PENDING), ...over }
}

describe('which actions a task offers', () => {
  it('pause and run for a scheduled task, resume and run for a paused one', () => {
    expect(taskActions(PENDING)).toEqual(['pause', 'run'])
    expect(taskActions(PAUSED_TASK)).toEqual(['resume', 'run'])
  })

  it('none for a task that is done, failed or of unknown status', () => {
    for (const status of ['completed', 'failed', 'cancelled', 'processing', null])
      expect(taskActions(task({ status }))).toEqual([])
  })
})

describe('the confirmation for a task', () => {
  it('pause names the task, says it is scheduled and when it runs next', () => {
    const c = taskConfirmation('pause', PENDING, now)
    expect(c.title).toBe(`Pause ${taskName(PENDING)}?`)
    expect(c.state).toMatch(/^Now: scheduled, next run today at \d\d:\d\d CET\.$/)
    expect(c.effect).toContain('won’t run until it is resumed')
    expect(c.warning).toBeNull()
    expect([c.verb, c.busyVerb]).toEqual(['Pause', 'Pausing…'])
    expect(c.path).toBe(`/api/tasks/${PENDING.id}/pause`)
  })

  it('resume of an overdue task warns that it runs once now (F9)', () => {
    const c = taskConfirmation('resume', PAUSED_TASK, now)
    expect(c.title).toBe('Resume documentation-summary?')
    expect(c.state).toBe('Now: paused. Its next run was due 27 May at 09:03 CEST.')
    expect(c.warning).toBe('Its run is overdue, so it runs once now, as soon as it is resumed.')
    expect(c.warning).toContain('runs once now')
    expect(c.effect).toBe('After that run it runs at 09:03 every day.')
  })

  it('resume of a paused task that is not overdue has no warning', () => {
    const c = taskConfirmation(
      'resume',
      task({ status: 'paused', overdue_on_resume: false, next_run_at: null }),
      now,
    )
    expect(c.state).toBe('Now: paused.')
    expect(c.warning).toBeNull()
    expect(c.effect).toMatch(/^It runs .* again\.$/)
  })

  it('an overdue task with no due time still says it is due', () => {
    const c = taskConfirmation('resume', { ...PAUSED_TASK, process_after: null }, now)
    expect(c.state).toBe('Now: paused, and its next run is already due.')
  })

  it('a task with no schedule words falls back to its schedule', () => {
    const t = { ...PAUSED_TASK, schedule: { ...PAUSED_TASK.schedule, words: null } }
    expect(taskConfirmation('resume', t, now).effect).toBe(
      'After that run it runs on its schedule.',
    )
  })

  it('a task with no next run says only its status', () => {
    expect(taskConfirmation('run', task({ next_run_at: null }), now).state).toBe('Now: scheduled.')
  })

  it('run warns that it spends tokens and does not change the schedule', () => {
    const c = taskConfirmation('run', PAUSED_TASK, now)
    expect(c.title).toBe('Run documentation-summary now?')
    expect(c.warning).toBe('A run spends tokens; it does not change the schedule.')
    expect(c.effect).toContain('Asking again queues another')
    expect(c.verb).toBe('Run now')
  })

  it('ids are encoded into the path', () => {
    expect(taskConfirmation('run', task({ id: 'a b' }), now).path).toBe('/api/tasks/a%20b/run')
  })
})

describe('the confirmation for a group', () => {
  it('restart says how many sessions run and that it interrupts a running turn', () => {
    const c = groupConfirmation(MAIN)
    expect(c.title).toBe('Restart main-group?')
    expect(c.state).toBe('Now: one of its six sessions is running.')
    expect(c.warning).toBe('A restart interrupts a running turn: the agent stops mid-reply.')
    expect(c.path).toBe(`/api/groups/${MAIN.id}/restart`)
  })

  it('with nothing running it still names the risk, and says nothing stops', () => {
    const c = groupConfirmation(IDLE)
    expect(c.state).toBe('Now: it has no sessions, so nothing is running.')
    expect(c.warning).toContain('interrupts a running turn')
    expect(c.warning).toContain('nothing stops')
    const state = (total: number, running: number) =>
      groupConfirmation({ ...IDLE, sessions: { total, running } }).state
    expect(state(1, 0)).toBe('Now: its one session is not running.')
    expect(state(1, 1)).toBe('Now: its one session is running.')
    expect(state(3, 0)).toBe('Now: none of its three sessions is running.')
    expect(state(3, 2)).toBe('Now: two of its three sessions are running.')
  })
})

describe('what the page says after an answer', () => {
  const words = (action: ActionName, result: string, extra = {}) =>
    outcomeWords(action, { status: 200, result, ...extra })

  it('done, in words for each action', () => {
    expect(words('pause', 'done')).toEqual({
      tone: 'success',
      text: 'Paused. It won’t run until you resume it.',
      closes: true,
    })
    expect(words('resume', 'done').text).toBe('Resumed. It runs on its schedule again.')
    expect(words('run', 'done').text).toMatch(/^One run is queued/)
    expect(words('restart', 'done', { detail: { restarted: 2 } }).text).toBe(
      'Restarted two containers.',
    )
    expect(words('restart', 'done', { detail: { restarted: 1 } }).text).toBe(
      'Restarted one container.',
    )
    expect(words('restart', 'done', { detail: { restarted: 0 } })).toEqual({
      tone: 'info',
      text: 'No container was running, so nothing was restarted.',
      closes: true,
    })
    expect(words('restart', 'done').tone).toBe('info')
  })

  it('already in that state, in plain words', () => {
    expect(words('pause', 'already_in_state')).toEqual({
      tone: 'info',
      text: 'It was already paused, so nothing changed.',
      closes: true,
    })
    expect(words('resume', 'already_in_state').text).toBe(
      'It was already scheduled, so nothing changed.',
    )
  })

  it('not found, no waiting run and a missed audit file close the dialog with a caution', () => {
    expect(words('run', 'not_found').text).toBe(
      'NanoClaw has no such task any more, so nothing changed.',
    )
    expect(words('restart', 'not_found').text).toContain('no such group')
    expect(words('pause', 'no_live_run').text).toBe(
      'It has no waiting run to pause right now; it may be running. Try again when the run finishes.',
    )
    expect(words('run', 'audit_failed')).toMatchObject({ tone: 'caution', closes: true })
  })

  it('everything that did not act keeps the dialog open with an error', () => {
    for (const [result, extra, expected] of [
      ['busy', {}, 'already running'],
      ['audit_unavailable', {}, 'can’t write its audit log, so it didn’t act'],
      ['refused', { reason: 'origin' }, 'did not come from the console’s own address'],
      ['refused', { reason: 'something new' }, 'not one the console accepts'],
      ['refused', {}, 'not one the console accepts'],
      ['broker_error', { code: 'timeout' }, '(timeout). It may or may not have happened'],
      ['broker_error', {}, '(unknown)'],
      ['broker_error', { code: 'unknown_verb' }, 'doesn’t offer this action'],
      ['signed_out', {}, 'sign-in may have ended'],
      ['network', {}, 'Couldn’t reach the console’s API'],
      ['teapot', {}, 'doesn’t know (200)'],
    ] as const) {
      const outcome = words('run', result, extra)
      expect(outcome.tone).toBe('error')
      expect(outcome.closes).toBe(false)
      expect(outcome.text).toContain(expected)
    }
    expect(outcomeWords('run', { status: null, result: 'teapot' }).text).toContain('no status')
  })
})

describe('the audit page’s words', () => {
  const entries = auditView().entries
  const blank: AuditEntry = { ...entries[0]!, action: null, result: null, detail: null }

  it('names each action', () => {
    expect(entries.map(auditActionWords)).toEqual([
      'Restart',
      'Run now',
      'Pause',
      'Resume',
      'Run now',
      'Run now',
    ])
    expect(auditActionWords(blank)).toBe('Unknown action')
    expect(auditActionWords({ ...blank, action: 'dance' })).toBe('dance')
  })

  it('says what came of each, plain when done', () => {
    expect(entries.map((e) => auditResultWords(e))).toEqual([
      { tone: null, text: 'Done; one container restarted' },
      { tone: null, text: 'Done; one run queued' },
      { tone: 'info', text: 'Already in that state; nothing changed' },
      { tone: 'error', text: 'Refused: it did not come from the console’s own address' },
      { tone: 'error', text: 'No answer from NanoClaw (timeout)' },
      { tone: 'error', text: 'Refused: the id is not one NanoClaw uses' },
    ])
    const restart = { ...entries[0]!, detail: { restarted: 0 } }
    expect(auditResultWords(restart).text).toBe('Done; no container was running')
    expect(auditResultWords({ ...restart, detail: { restarted: 3 } }).text).toBe(
      'Done; three containers restarted',
    )
    expect(auditResultWords({ ...entries[2]!, result: 'done' }).text).toBe('Done')
    for (const [result, text] of [
      ['not_found', 'Not found; nothing changed'],
      ['no_live_run', 'No waiting run to change'],
      ['busy', 'Refused: the same action was still running'],
      ['audit_failed', 'audit_failed'],
    ] as const)
      expect(auditResultWords({ ...blank, result }).text).toBe(text)
    expect(auditResultWords(blank)).toEqual({ tone: 'error', text: 'No result recorded' })
    expect(auditResultWords({ ...blank, result: 'broker_error' }).text).toContain('(unknown)')
  })

  it('links a target to its page, and nothing for an id it did not keep', () => {
    expect(entries.map(auditTargetPath)).toEqual([
      `/groups/${entries[0]!.target.id}`,
      `/tasks/${entries[1]!.target.id}`,
      `/tasks/${PAUSED_TASK.id}`,
      `/tasks/${PAUSED_TASK.id}`,
      `/tasks/${PAUSED_TASK.id}`,
      null,
    ])
    expect(auditTargetPath({ ...blank, target: { type: 'thing', id: 'x' } })).toBeNull()
  })

  it('answers with how many and when the last was', () => {
    expect(auditAnswer([], now)).toBe('Nothing has been done from the console yet.')
    expect(auditAnswer(entries, now)).toBe('Six attempts recorded; the last today at 15:25 CET.')
    expect(auditAnswer(entries.slice(0, 1), now)).toBe(
      'One attempt recorded; the last today at 15:25 CET.',
    )
    const many = Array.from({ length: 12 }, () => entries[0]!)
    expect(auditAnswer(many, now)).toMatch(/^12 attempts recorded/)
    expect(auditAnswer([{ ...blank, at: null }], now)).toBe('One attempt recorded.')
  })
})
