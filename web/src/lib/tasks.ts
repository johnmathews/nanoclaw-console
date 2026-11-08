import type { Task } from './types'

const EXCERPT = 60

/** A readable name: the task file without `.md`, else the start of the prompt, else the id. */
export function taskName(task: Task): string {
  if (task.task_file) return task.task_file.replace(/\.md$/i, '')
  const prompt = task.prompt?.trim().replace(/\s+/g, ' ')
  if (!prompt) return task.id
  if (prompt.length <= EXCERPT) return prompt
  const cut = prompt.slice(0, EXCERPT + 1)
  const space = cut.lastIndexOf(' ')
  return `${(space > 0 ? cut.slice(0, space) : cut.slice(0, EXCERPT)).replace(/[\s,.;:]+$/, '')}…`
}

/** The exact words the plan asks for (W8, F9): a resume fires one catch-up run at once. */
export const OVERDUE_WORDS = 'Paused — will run once immediately if resumed'

const STATUS: Record<string, string> = {
  pending: 'Scheduled',
  active: 'Scheduled',
  running: 'Running now',
  processing: 'Running now',
  paused: 'Paused',
  completed: 'Done',
  done: 'Done',
  failed: 'Failed',
  cancelled: 'Cancelled',
  canceled: 'Cancelled',
}

export function statusWords(task: Task): string {
  if (task.overdue_on_resume) return OVERDUE_WORDS
  if (task.status === null) return 'Status unknown'
  const known = STATUS[task.status]
  if (known) return known
  const words = task.status.replace(/[_-]+/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** Figures, since this sits in a table: "123 runs, 3 failed". */
export function runsWords(task: Task): string {
  if (task.runs === null) return 'Not known'
  if (task.runs === 0) return 'No runs yet'
  const runs = `${task.runs} ${task.runs === 1 ? 'run' : 'runs'}`
  const failed = task.failed_runs ?? 0
  return `${runs}, ${failed === 0 ? 'none failed' : `${failed} failed`}`
}
