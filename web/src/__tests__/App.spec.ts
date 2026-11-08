import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { overview, taskList } from '../fixtures/api'
import { mountApp, text, useClock } from './mountApp'

describe('the app shell', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('names the product and links each page, marking the current one', async () => {
    const wrapper = await mountApp('/tasks', { '/api/tasks': taskList() })
    expect(text(wrapper, '#app-name')).toBe('NanoClaw console')
    const links = wrapper.findAll('#app-nav a')
    expect(links.map((a) => a.text())).toEqual([
      'Overview',
      'Tasks',
      'Groups',
      'Permissions',
      'Problems',
    ])
    expect(wrapper.find('#nav-tasks').attributes('aria-current')).toBe('page')
    expect(wrapper.find('#nav-overview').attributes('aria-current')).toBeUndefined()
  })

  it('keeps Tasks marked on a task’s own page', async () => {
    const wrapper = await mountApp('/tasks/task-x', {})
    expect(wrapper.find('#nav-tasks').attributes('data-active')).toBe('true')
  })

  it('keeps Groups marked on a group’s own page', async () => {
    const wrapper = await mountApp('/groups/ag-x', {})
    expect(wrapper.find('#nav-groups').attributes('data-active')).toBe('true')
    expect(wrapper.find('#nav-groups').attributes('aria-current')).toBeUndefined()
  })

  it('offers a skip link to the page', async () => {
    const wrapper = await mountApp('/', { '/api/overview': overview() })
    const skip = wrapper.find('#skip-link')
    expect(skip.attributes('href')).toBe('#main')
    expect(wrapper.find('main#main').exists()).toBe(true)
  })

  it('has one h1 per page, and names the page in the title', async () => {
    const wrapper = await mountApp('/', { '/api/overview': overview() })
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(document.title).toBe('Overview · NanoClaw console')
  })

  it('says when a page does not exist', async () => {
    const wrapper = await mountApp('/nope', {})
    expect(text(wrapper, 'h1')).toBe('Page not found')
    expect(wrapper.find('#not-found-home').attributes('href')).toBe('/')
  })
})
