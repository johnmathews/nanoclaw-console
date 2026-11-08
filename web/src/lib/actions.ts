import type { ActionAnswer } from './api'
import { taskName, statusWords } from './tasks'
import { formatWhen, numberWords } from './time'
import type { AuditEntry, Group, Task } from './types'
import { groupName } from './groups'

/**
 * Release 2's four actions in words (architecture.md §5.8): what each confirmation says, and what
 * the page says once the API has answered. Every string follows voice.md: the facts first, then
 * what happens, and no "Are you sure".
 */

export type ActionName = 'pause' | 'resume' | 'run' | 'restart'

/** What a ConfirmDialog shows. `warning` is the caution line the plan asks for, word for word. */
export type Confirmation = {
  action: ActionName
  path: string
  title: string
  state: string
  effect: string
  warning: string | null
  verb: string
  busyVerb: string
}

/** What the page says once the API answered. A `closes` answer shuts the dialog and refreshes. */
export type ActionOutcome = {
  tone: 'success' | 'info' | 'caution' | 'error'
  text: string
  closes: boolean
}

/** The schedule in a sentence's middle: "At 09:03 every day" → "at 09:03 every day". */
function lower(words: string | null): string {
  return words ? words.charAt(0).toLowerCase() + words.slice(1) : 'on its schedule'
}

/** The words for the task's state now, shown in each task dialog. */
function taskState(task: Task, now: Date): string {
  if (task.overdue_on_resume)
    return task.process_after
      ? `Now: paused. Its next run was due ${formatWhen(task.process_after, now)}.`
      : 'Now: paused, and its next run is already due.'
  if (task.status === 'paused') return 'Now: paused.'
  if (task.next_run_at)
    return `Now: ${statusWords(task).toLowerCase()}, next run ${formatWhen(task.next_run_at, now)}.`
  return `Now: ${statusWords(task).toLowerCase()}.`
}

/** The actions a task offers: pause or resume by its status, and run while it is live. */
export function taskActions(task: Task): ActionName[] {
  const actions: ActionName[] = []
  if (task.status === 'pending') actions.push('pause')
  if (task.status === 'paused') actions.push('resume')
  if (task.status === 'pending' || task.status === 'paused') actions.push('run')
  return actions
}

export function taskConfirmation(action: ActionName, task: Task, now: Date): Confirmation {
  const name = taskName(task)
  const path = `/api/tasks/${encodeURIComponent(task.id)}/${action}`
  const state = taskState(task, now)
  if (action === 'pause')
    return {
      action,
      path,
      title: `Pause ${name}?`,
      state,
      effect: 'It won’t run until it is resumed. Its schedule and run history stay as they are.',
      warning: null,
      verb: 'Pause',
      busyVerb: 'Pausing…',
    }
  if (action === 'resume')
    return {
      action,
      path,
      title: `Resume ${name}?`,
      state,
      effect: task.overdue_on_resume
        ? `After that run it runs ${lower(task.schedule.words)}.`
        : `It runs ${lower(task.schedule.words)} again.`,
      warning: task.overdue_on_resume
        ? 'Its run is overdue, so it runs once now, as soon as it is resumed.'
        : null,
      verb: 'Resume',
      busyVerb: 'Resuming…',
    }
  return {
    action: 'run',
    path,
    title: `Run ${name} now?`,
    state,
    effect: 'One extra run is queued straight away. Asking again queues another.',
    warning: 'A run spends tokens; it does not change the schedule.',
    verb: 'Run now',
    busyVerb: 'Queuing…',
  }
}

/** "Now: one of its six sessions is running." */
function sessionsState(running: number, total: number): string {
  if (total === 0) return 'Now: it has no sessions, so nothing is running.'
  if (total === 1) return `Now: its one session is ${running ? '' : 'not '}running.`
  if (running === 0) return `Now: none of its ${numberWords(total)} sessions is running.`
  return `Now: ${numberWords(running)} of its ${numberWords(total)} sessions ${running === 1 ? 'is' : 'are'} running.`
}

export function groupConfirmation(group: Group): Confirmation {
  const name = groupName(group)
  const { running, total } = group.sessions
  return {
    action: 'restart',
    path: `/api/groups/${encodeURIComponent(group.id)}/restart`,
    title: `Restart ${name}?`,
    state: sessionsState(running, total),
    effect:
      'Each running container stops. One with messages waiting starts again at once; the rest on their next message.',
    warning:
      running > 0
        ? 'A restart interrupts a running turn: the agent stops mid-reply.'
        : 'A restart interrupts a running turn; none is running now, so nothing stops.',
    verb: 'Restart',
    busyVerb: 'Restarting…',
  }
}

const REASONS: Record<string, string> = {
  action_header: 'the console’s action header was missing',
  origin: 'it did not come from the console’s own address',
  fetch_site: 'it was not sent by the console’s own page',
  content_type: 'it was not sent as JSON',
  body: 'its body was not empty JSON',
  bad_id: 'the id is not one NanoClaw uses',
}

function reasonWords(reason: string | null | undefined): string {
  return (reason && REASONS[reason]) ?? 'it was not one the console accepts'
}

/** The page's words for the API's answer to an action. */
export function outcomeWords(action: ActionName, answer: ActionAnswer): ActionOutcome {
  const done = (text: string): ActionOutcome => ({ tone: 'success', text, closes: true })
  switch (answer.result) {
    case 'done': {
      if (action === 'pause') return done('Paused. It won’t run until you resume it.')
      if (action === 'resume') return done('Resumed. It runs on its schedule again.')
      if (action === 'run')
        return done('One run is queued. It shows in the run log below when it finishes.')
      const n = Number(answer.detail?.restarted ?? 0)
      return n > 0
        ? done(`Restarted ${numberWords(n)} ${n === 1 ? 'container' : 'containers'}.`)
        : {
            tone: 'info',
            text: 'No container was running, so nothing was restarted.',
            closes: true,
          }
    }
    case 'already_in_state':
      return {
        tone: 'info',
        text:
          action === 'pause'
            ? 'It was already paused, so nothing changed.'
            : 'It was already scheduled, so nothing changed.',
        closes: true,
      }
    case 'not_found':
      return {
        tone: 'caution',
        text:
          action === 'restart'
            ? 'NanoClaw has no such group any more, so nothing was restarted.'
            : 'NanoClaw has no such task any more, so nothing changed.',
        closes: true,
      }
    case 'no_live_run':
      return {
        tone: 'caution',
        text: `It has no waiting run to ${action} right now; it may be running. Try again when the run finishes.`,
        closes: true,
      }
    case 'audit_failed':
      return {
        tone: 'caution',
        text: 'NanoClaw acted, but the audit file missed it; the console’s own log has the line.',
        closes: true,
      }
    case 'busy':
      return {
        tone: 'error',
        text: 'This action is already running for it. Wait for that to finish.',
        closes: false,
      }
    case 'audit_unavailable':
      return {
        tone: 'error',
        text: 'The console can’t write its audit log, so it didn’t act. Nothing changed.',
        closes: false,
      }
    case 'refused':
      return {
        tone: 'error',
        text: `The console refused the request: ${reasonWords(answer.reason)}. Reload the page and try again.`,
        closes: false,
      }
    case 'broker_error':
      return {
        tone: 'error',
        text:
          answer.code === 'unknown_verb'
            ? 'The broker doesn’t offer this action, so nothing changed. It may be an older broker.'
            : `Couldn’t get an answer from NanoClaw (${answer.code ?? 'unknown'}). It may or may not have happened; the page shows what NanoClaw has now.`,
        closes: false,
      }
    case 'signed_out':
      return {
        tone: 'error',
        text: 'The Access sign-in may have ended. Reload the page, then try again.',
        closes: false,
      }
    case 'network':
      return {
        tone: 'error',
        text: 'Couldn’t reach the console’s API, so nothing is known to have changed. Try again.',
        closes: false,
      }
    default:
      return {
        tone: 'error',
        text: `The console answered in a way this page doesn’t know (${answer.status ?? 'no status'}). Reload the page to see what changed.`,
        closes: false,
      }
  }
}

// --- the audit page -------------------------------------------------------------------------

const ACTION_WORDS: Record<string, string> = {
  pause: 'Pause',
  resume: 'Resume',
  run: 'Run now',
  restart: 'Restart',
}

export function auditActionWords(entry: AuditEntry): string {
  return (entry.action && ACTION_WORDS[entry.action]) ?? entry.action ?? 'Unknown action'
}

/** One entry's result in a few words, and its tone: plain when it was done. */
export function auditResultWords(entry: AuditEntry): {
  tone: ActionOutcome['tone'] | null
  text: string
} {
  switch (entry.result) {
    case 'done': {
      const restarted = entry.detail?.restarted
      if (entry.action === 'restart' && typeof restarted === 'number')
        return {
          tone: null,
          text:
            restarted === 0
              ? 'Done; no container was running'
              : `Done; ${numberWords(restarted)} ${restarted === 1 ? 'container' : 'containers'} restarted`,
        }
      return { tone: null, text: entry.action === 'run' ? 'Done; one run queued' : 'Done' }
    }
    case 'already_in_state':
      return { tone: 'info', text: 'Already in that state; nothing changed' }
    case 'not_found':
      return { tone: 'caution', text: 'Not found; nothing changed' }
    case 'no_live_run':
      return { tone: 'caution', text: 'No waiting run to change' }
    case 'busy':
      return { tone: 'caution', text: 'Refused: the same action was still running' }
    case 'refused':
      return { tone: 'error', text: `Refused: ${reasonWords(entry.reason)}` }
    case 'broker_error':
      return { tone: 'error', text: `No answer from NanoClaw (${entry.code ?? 'unknown'})` }
    default:
      return { tone: 'error', text: entry.result ?? 'No result recorded' }
  }
}

/** Where an entry's target lives in the console, or null for an id the log did not keep. */
export function auditTargetPath(entry: AuditEntry): string | null {
  const id = entry.target.id
  if (!id) return null
  if (entry.target.type === 'task') return `/tasks/${encodeURIComponent(id)}`
  if (entry.target.type === 'group') return `/groups/${encodeURIComponent(id)}`
  return null
}

export function auditAnswer(entries: AuditEntry[], now: Date): string {
  if (!entries.length) return 'Nothing has been done from the console yet.'
  const n = entries.length
  const last = entries[0]?.at
  const count =
    n === 1
      ? 'One attempt'
      : `${n <= 10 ? numberWords(n).replace(/^./, (c) => c.toUpperCase()) : n} attempts`
  return last ? `${count} recorded; the last ${formatWhen(last, now)}.` : `${count} recorded.`
}
