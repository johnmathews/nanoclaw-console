import { describe, expect, it } from 'vitest'
import { PAUSED_TASK, TASKS } from '../../fixtures/api'
import type { Task } from '../types'
import { runsWords, statusWords, taskName } from '../tasks'

function task(changes: Partial<Task>): Task {
  return { ...structuredClone(PAUSED_TASK), ...changes }
}

describe('taskName', () => {
  it('is the task file without .md', () => {
    expect(taskName(PAUSED_TASK)).toBe('documentation-summary')
  })

  it('is an excerpt of the prompt, cut at a word, when no file is named', () => {
    const inbox = TASKS.find((t) => t.task_file === null && t.prompt?.startsWith('Check'))!
    expect(taskName(inbox)).toBe('Check the shared inbox for anything addressed to the server…')
  })

  it('is the whole prompt when it is short', () => {
    expect(taskName(task({ task_file: null, prompt: 'Remind John.' }))).toBe('Remind John.')
  })

  it('is the id when there is neither', () => {
    expect(taskName(task({ task_file: null, prompt: null }))).toBe(PAUSED_TASK.id)
    expect(taskName(task({ task_file: null, prompt: '   ' }))).toBe(PAUSED_TASK.id)
  })
})

describe('statusWords', () => {
  it('warns that a paused, overdue task runs once at once on resume', () => {
    expect(statusWords(PAUSED_TASK)).toBe('Paused — will run once immediately if resumed')
  })

  it('says paused otherwise', () => {
    expect(statusWords(task({ overdue_on_resume: false }))).toBe('Paused')
  })

  it('names each other status', () => {
    expect(statusWords(task({ status: 'pending', overdue_on_resume: false }))).toBe('Scheduled')
    expect(statusWords(task({ status: 'running', overdue_on_resume: false }))).toBe('Running now')
    expect(statusWords(task({ status: 'completed', overdue_on_resume: false }))).toBe('Done')
    expect(statusWords(task({ status: 'failed', overdue_on_resume: false }))).toBe('Failed')
    expect(statusWords(task({ status: 'cancelled', overdue_on_resume: false }))).toBe('Cancelled')
    expect(statusWords(task({ status: 'odd_state', overdue_on_resume: false }))).toBe('Odd state')
    expect(statusWords(task({ status: null, overdue_on_resume: false }))).toBe('Status unknown')
  })
})

describe('runsWords', () => {
  it('counts runs and failures in figures', () => {
    expect(runsWords(task({ runs: 5, failed_runs: 0 }))).toBe('5 runs, none failed')
    expect(runsWords(task({ runs: 123, failed_runs: 3 }))).toBe('123 runs, 3 failed')
    expect(runsWords(task({ runs: 1, failed_runs: 1 }))).toBe('1 run, 1 failed')
    expect(runsWords(task({ runs: 0, failed_runs: 0 }))).toBe('No runs yet')
    expect(runsWords(task({ runs: null, failed_runs: null }))).toBe('Not known')
  })
})

describe('the edges', () => {
  it('cuts a prompt with no space in it at the limit', () => {
    expect(taskName(task({ task_file: null, prompt: 'x'.repeat(80) }))).toBe(`${'x'.repeat(60)}…`)
  })

  it('treats a null failure count as none', () => {
    expect(runsWords(task({ runs: 2, failed_runs: null }))).toBe('2 runs, none failed')
  })
})
