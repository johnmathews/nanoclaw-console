// The secret-absence test (W9): the mock API plants a Bearer token in fields the web app never
// shows, as if broker redaction had missed it. No page may carry it anywhere in its DOM: text,
// attributes, titles or hidden elements.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  GROUP_IDS,
  groupsView,
  overview,
  permissionsView,
  PLANTED_MARK,
  PLANTED_TOKEN,
  problemsView,
} from '../fixtures/api'
import { mountApp, useClock } from './mountApp'

const ANSWERS = {
  '/api/overview': overview(),
  '/api/groups': groupsView(),
  '/api/permissions': permissionsView(),
  '/api/problems': problemsView(),
}

const PAGES = [
  '/',
  '/groups',
  ...Object.values(GROUP_IDS).map((id) => `/groups/${id}`),
  '/permissions',
  '/problems',
]

describe('no page shows a planted secret', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('the fixtures really carry the token', () => {
    const all = JSON.stringify([overview(), groupsView(), permissionsView(), problemsView()])
    expect(all.split(PLANTED_TOKEN).length - 1).toBeGreaterThanOrEqual(10)
  })

  for (const path of PAGES) {
    it(`${path} renders no planted token`, async () => {
      const wrapper = await mountApp(path, ANSWERS)
      expect(wrapper.find('h1').text()).not.toBe('Page not found')
      const dom = document.documentElement.outerHTML
      expect(dom).not.toContain(PLANTED_MARK)
      expect(dom).not.toContain('Bearer ')
    })
  }
})
