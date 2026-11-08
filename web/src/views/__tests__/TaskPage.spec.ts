import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PAUSED_TASK, TASKS, taskDetail } from '../../fixtures/api'
import { mountApp, text, useClock } from '../../__tests__/mountApp'

const MEMORY = TASKS[1]!
const INBOX = TASKS[0]!

async function open(id: string, body: unknown = taskDetail(id)) {
  return mountApp(`/tasks/${id}`, { [`/api/tasks/${id}`]: body })
}

describe('a task’s page', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('is named after the task, with a way back to the list', async () => {
    const wrapper = await open(PAUSED_TASK.id)
    expect(text(wrapper, 'h1')).toBe('documentation-summary')
    expect(wrapper.find('#task-back').attributes('href')).toBe('/tasks')
    expect(document.title).toBe('documentation-summary · NanoClaw console')
  })

  it('warns, with when it last ran, that resuming runs it at once', async () => {
    const wrapper = await open(PAUSED_TASK.id)
    expect(text(wrapper, '#task-status')).toBe('Paused') // the full warning follows, once
    expect(text(wrapper, '#task-overdue')).toBe(
      'Paused — will run once immediately if resumed. It last ran 26 May at 09:03 CEST; after that one run it runs at 09:03 every day.',
    )
  })

  it('shows what it will do: the task file, rendered safely', async () => {
    const wrapper = await open(PAUSED_TASK.id)
    const file = wrapper.find('#task-file-content')
    expect(file.find('h3').text()).toBe('Documentation summary')
    expect(file.find('strong').text()).toBe('five-line summary')
    expect(file.html()).not.toMatch(/<script|<img|javascript:|tracker\.example/)
    // The planted javascript: link keeps its words and loses its target; the real one keeps both.
    expect(file.findAll('a').map((a) => a.attributes('href'))).toEqual([
      undefined,
      'https://docs.example.com/runbook',
    ])
    expect(file.text()).toContain('A planted link')
    expect(text(wrapper, '#task-file-name')).toBe('tasks/documentation-summary.md')
  })

  it('shows the full prompt', async () => {
    const wrapper = await open(INBOX.id)
    expect(text(wrapper, '#task-prompt')).toBe(INBOX.prompt)
  })

  it('says when the prompt names no file', async () => {
    const wrapper = await open(INBOX.id)
    expect(text(wrapper, '#task-file')).toContain(
      'The prompt names no task file, so the prompt below is everything it does.',
    )
  })

  it('says when the named file could not be read', async () => {
    const body = taskDetail(PAUSED_TASK.id)
    body.task_file = null
    body.sources = { broker: { ok: false, errors: { 'task-file': 'unknown_verb' } } }
    const wrapper = await open(PAUSED_TASK.id, body)
    expect(text(wrapper, '#task-file')).toContain('Couldn’t read tasks/documentation-summary.md.')
  })

  it('says when the named file is missing', async () => {
    const body = taskDetail(PAUSED_TASK.id)
    body.task_file = null
    const wrapper = await open(PAUSED_TASK.id, body)
    expect(text(wrapper, '#task-file')).toContain(
      'tasks/documentation-summary.md isn’t in the group’s folder, so the agent will find nothing to follow.',
    )
  })

  it('says a script runs, without showing it', async () => {
    const wrapper = await open(INBOX.id)
    expect(text(wrapper, '#task-script')).toBe(
      'This task also runs a script. The console doesn’t show scripts.',
    )
  })

  it('shows the recent run log and the run stats', async () => {
    const wrapper = await open(MEMORY.id)
    const lines = wrapper.findAll('#task-run-log li')
    expect(lines.map((l) => l.text())).toEqual(taskDetail(MEMORY.id).task.recent_log)
    expect(text(wrapper, '#task-runs')).toBe('123')
    expect(text(wrapper, '#task-failed-runs')).toBe('3')
    expect(text(wrapper, '#task-series-started')).toBe('8 July at 12:00 CEST (four months ago)')
  })

  it('says when no run is logged', async () => {
    const wrapper = await open(PAUSED_TASK.id)
    expect(text(wrapper, '#task-run-log-empty')).toBe('No run log yet.')
  })

  it('says when there is no such task', async () => {
    const wrapper = await mountApp('/tasks/task-gone', { '/api/tasks/task-gone': 404 })
    expect(text(wrapper, 'h1')).toBe('Task not found')
    expect(text(wrapper, '#task-missing')).toContain('There is no task task-gone.')
  })

  it('says when the broker cannot answer', async () => {
    const wrapper = await mountApp('/tasks/task-x', { '/api/tasks/task-x': 503 })
    expect(text(wrapper, '#page-banner')).toBe(
      'Couldn’t reach the broker, so this task can’t be shown. It retries every 30 seconds.',
    )
  })
})

describe('a task’s page, edge states', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('says when the file was cut short, and what is not known', async () => {
    const body = taskDetail(PAUSED_TASK.id)
    body.task_file!.truncated = true
    Object.assign(body.task, {
      last_run_at: null,
      prompt: null,
      completed_runs: null,
      runs: null,
      failed_runs: null,
      tries: null,
      series_started_at: null,
      session_id: null,
      row_id: null,
      group: { id: null, name: null, folder: null },
      schedule: { ...body.task.schedule, words: null, cron: null },
    })
    const wrapper = await open(PAUSED_TASK.id, body)
    expect(text(wrapper, '#task-file')).toContain('The file is longer than the console reads')
    expect(text(wrapper, '#task-overdue')).toBe(
      'Paused — will run once immediately if resumed. After that one run it runs on its schedule.',
    )
    expect(text(wrapper, '#task-prompt')).toBe('No prompt')
    expect(text(wrapper, '#task-runs')).toBe('Not known')
    expect(text(wrapper, '#task-last-run')).toBe('Never')
    expect(text(wrapper, '#task-next-run')).toBe('Not while paused')
    expect(text(wrapper, '#task-series-started')).toBe('Not known (the id carries no time)')
    expect(text(wrapper, '#task-session')).toBe('None')
    expect(text(wrapper, '#task-group')).toBe('Not in the group list')
  })

  it('shows a scheduled task’s next run', async () => {
    const wrapper = await open(MEMORY.id)
    expect(text(wrapper, '#task-next-run')).toBe('today at 17:00 CET (in two hours)')
    expect(text(wrapper, '#task-schedule')).toBe(
      'At 17:00 every day 0 17 * * *, in Europe/Amsterdam',
    )
  })

  it('treats an id the API does not know as not found', async () => {
    const wrapper = await mountApp('/tasks/task-slow', {})
    expect(wrapper.text()).toContain('Task not found')
  })
})
