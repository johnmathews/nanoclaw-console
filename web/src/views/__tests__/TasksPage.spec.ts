import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PAUSED_TASK, TASKS, taskList } from '../../fixtures/api'
import { mountApp, text, useClock } from '../../__tests__/mountApp'

const INBOX = TASKS[0]!
const MEMORY = TASKS[1]!
const DIGEST = TASKS[2]!

async function open(body: unknown = taskList()) {
  return mountApp('/tasks', { '/api/tasks': body })
}

describe('the tasks page', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('answers first: how many, how many paused, what runs next', async () => {
    const wrapper = await open()
    expect(text(wrapper, 'h1')).toBe('Scheduled tasks')
    expect(text(wrapper, '#tasks-answer')).toBe(
      'Six tasks. Two are paused, and each would run once straight away if resumed. Next: Check the shared inbox for anything addressed to the server…, today at 15:37 CET (in seven minutes).',
    )
  })

  it('lists every task by readable name, linked to its page', async () => {
    const wrapper = await open()
    const rows = wrapper.findAll('#tasks-table tbody tr')
    expect(rows).toHaveLength(6)
    const link = wrapper.find(`#task-row-${PAUSED_TASK.id} a`)
    expect(link.text()).toBe('documentation-summary')
    expect(link.attributes('href')).toBe(`/tasks/${PAUSED_TASK.id}`)
  })

  it('warns that the paused documentation summary runs at once if resumed', async () => {
    const wrapper = await open()
    expect(text(wrapper, `#task-row-${PAUSED_TASK.id} [data-col="status"]`)).toBe(
      'Paused — will run once immediately if resumed',
    )
    expect(text(wrapper, `#task-card-${PAUSED_TASK.id}`)).toContain(
      'Paused — will run once immediately if resumed',
    )
  })

  it('gives schedule in words with the cron, and times in Amsterdam with the zone', async () => {
    const wrapper = await open()
    const row = `#task-row-${PAUSED_TASK.id}`
    expect(text(wrapper, `${row} [data-col="schedule"]`)).toBe('At 09:03 every day 3 9 * * *')
    expect(text(wrapper, `${row} [data-col="next"]`)).toBe('Not while paused')
    expect(text(wrapper, `${row} [data-col="last"]`)).toBe('26 May at 09:03 CEST five months ago')
    expect(text(wrapper, `#task-row-${INBOX.id} [data-col="next"]`)).toBe(
      'today at 15:37 CET in seven minutes',
    )
  })

  it('counts runs and failures, and names the group', async () => {
    const wrapper = await open()
    expect(text(wrapper, `#task-row-${MEMORY.id} [data-col="runs"]`)).toBe('123 runs, 3 failed')
    expect(text(wrapper, `#task-row-${MEMORY.id} [data-col="group"]`)).toBe('server-bot')
    expect(text(wrapper, `#task-row-${DIGEST.id} [data-col="group"]`)).toBe('Not in the group list')
    expect(text(wrapper, `#task-row-${DIGEST.id} [data-col="last"]`)).toBe('Never')
  })

  it('draws each task as a card for a phone too', async () => {
    const wrapper = await open()
    expect(wrapper.findAll('#tasks-cards > li')).toHaveLength(6)
    expect(text(wrapper, `#task-card-${MEMORY.id}`)).toContain('123 runs, 3 failed')
  })

  it('says there are none when the list is empty', async () => {
    const body = taskList()
    body.tasks = []
    const wrapper = await open(body)
    expect(text(wrapper, '#tasks-answer')).toBe('No scheduled tasks.')
    expect(wrapper.find('#tasks-table').exists()).toBe(false)
  })

  it('does not claim there are none when the list could not be read', async () => {
    const body = taskList()
    body.tasks = []
    body.sources = { broker: { ok: false, errors: { 'tasks-list': 'unavailable' } } }
    const wrapper = await open(body)
    expect(text(wrapper, '#tasks-answer')).toBe('Couldn’t read the task list.')
    expect(text(wrapper, '#page-sources')).toContain('the broker did not answer')
  })
})

describe('the tasks page, other mixes', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('words one paused task, and a pause that would not run at once', async () => {
    const one = taskList()
    one.tasks = one.tasks.filter((t) => t.id !== TASKS[5]!.id)
    const wrapper = await open(one)
    expect(text(wrapper, '#tasks-answer')).toContain(
      'Five tasks. One is paused, and would run once straight away if resumed.',
    )
    wrapper.unmount()

    const mixed = taskList()
    mixed.tasks[5] = { ...mixed.tasks[5]!, overdue_on_resume: false }
    const again = await open(mixed)
    expect(text(again, '#tasks-answer')).toContain(
      'Two are paused; one would run once straight away if resumed.',
    )
  })

  it('handles one task, with nothing scheduled and an unreadable schedule', async () => {
    const body = taskList()
    body.tasks = [
      {
        ...TASKS[3]!,
        status: 'completed',
        next_run_at: null,
        schedule: {
          cron: null,
          words: null,
          timezone: 'Europe/Amsterdam',
          valid: false,
          next_fire_at: null,
        },
      },
    ]
    const wrapper = await open(body)
    expect(text(wrapper, '#tasks-answer')).toBe('One task.')
    const row = `#task-row-${TASKS[3]!.id}`
    expect(text(wrapper, `${row} [data-col="next"]`)).toBe('Not scheduled')
    expect(text(wrapper, `${row} [data-col="schedule"]`)).toBe('Not readable')
  })
})
