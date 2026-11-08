// Shared set-up for the browser checks: the app with /api mocked, a theme, axe, and the
// measurements the specs repeat. Copied in shape from tracker's e2e/support.ts.
import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'
import { overview, taskDetail, taskList, TASKS } from '../src/fixtures/api.ts'

/** Longer than the slowest transition (120ms in the design system). */
export const SETTLE_MS = 400

export const THEMES = ['light', 'dark'] as const
export type Theme = (typeof THEMES)[number]

export const DESKTOP = { width: 1440, height: 900 }
export const PHONE = { width: 390, height: 844 }

/** A mocked answer: a body (status 200), or a status with an optional body. */
export type Answer = { status?: number; body?: unknown }

/**
 * The default API: every view from src/fixtures/api.ts, shaped exactly as architecture.md §4.7,
 * and each task's detail. Anything else under /api/ is a 404, as the real API answers.
 */
export function defaultAnswers(): Record<string, Answer> {
  const answers: Record<string, Answer> = {
    '/api/overview': { body: overview() },
    '/api/tasks': { body: taskList() },
  }
  for (const task of TASKS) answers[`/api/tasks/${task.id}`] = { body: taskDetail(task.id) }
  return answers
}

/** Open the app at `path` in a theme, with /api answered from `answers` (merged over the defaults). */
export async function openApp(
  page: Page,
  {
    theme,
    path = '/',
    answers = {},
  }: { theme: Theme; path?: string; answers?: Record<string, Answer> },
): Promise<void> {
  const table = { ...defaultAnswers(), ...answers }
  await page.emulateMedia({ colorScheme: theme })
  await page.route('**/api/**', (route) => {
    const answer = table[new URL(route.request().url()).pathname]
    return route.fulfill({
      status: answer ? (answer.status ?? 200) : 404,
      contentType: 'application/json',
      body: JSON.stringify(answer ? (answer.body ?? {}) : { error: 'not_found' }),
    })
  })
  await page.goto(path)
  await settle(page)
}

export async function settle(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(SETTLE_MS)
}

/** The page's --canvas token: proof the theme really switched, whatever paints the background. */
export function canvasToken(page: Page): Promise<string> {
  return page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim(),
  )
}

/** axe at WCAG 2.2 A and AA and its best practices; a failure lists each rule and its nodes. */
export async function expectNoAxeViolations(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa', 'best-practice'])
    .analyze()
  expect(
    violations.map((v) => {
      const nodes = v.nodes.slice(0, 3).map((n) => {
        // The summary's second line is the reason ("…insufficient color contrast of 2.65…").
        const reason = n.failureSummary?.split('\n')[1]?.trim()
        return `${n.target.join(' ')}${reason ? ` [${reason}]` : ''}`
      })
      const more = v.nodes.length > 3 ? `; and ${v.nodes.length - 3} more` : ''
      return `${v.id} (${v.impact}, ${v.nodes.length} nodes): ${nodes.join('; ')}${more}`
    }),
  ).toEqual([])
}

/** No sideways scroll: the page is no wider than the viewport. */
export async function expectNoSidewaysScroll(page: Page): Promise<void> {
  const size = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    inner: window.innerWidth,
  }))
  expect(size.scroll, 'the page scrolls sideways').toBeLessThanOrEqual(size.inner)
}
