// Accessibility gate (from the design-system skill's a11y.spec.ts, by way of tracker): axe (WCAG
// 2.2 A and AA, and its best practices) on every page in both themes at desktop and phone width,
// with /api mocked from src/fixtures/api.ts; no sideways scroll; and the page's own words for
// each answer the API can give.
//
// The theme is the app's `.dark` class on <html>, which tokens.css's dark block matches
// (`npm run tokens` passes --dark-selector .dark). The first test fails if switching it changes
// nothing, so a "dark" audit can never quietly re-run light.
import { expect, test } from '@playwright/test'
import { overviewDegraded, PAUSED_TASK } from '../src/fixtures/api.ts'
import {
  DESKTOP,
  PHONE,
  THEMES,
  canvasToken,
  expectNoAxeViolations,
  expectNoSidewaysScroll,
  openApp,
} from './support'

const PAGES = [
  { name: 'overview', path: '/', heading: 'Overview' },
  { name: 'tasks', path: '/tasks', heading: 'Scheduled tasks' },
  { name: 'a task', path: `/tasks/${PAUSED_TASK.id}`, heading: 'documentation-summary' },
] as const

test('dark really is dark', async ({ page, context }) => {
  await openApp(page, { theme: 'light' })
  const light = await canvasToken(page)
  const dark = await context.newPage()
  await openApp(dark, { theme: 'dark' })
  expect(await dark.evaluate(() => document.documentElement.classList.contains('dark'))).toBe(true)
  expect(await canvasToken(dark), '--canvas is identical in both themes').not.toBe(light)
})

for (const theme of THEMES) {
  for (const [width, size] of [
    ['desktop', DESKTOP],
    ['phone', PHONE],
  ] as const) {
    for (const p of PAGES) {
      test(`${p.name} passes axe, ${width}, ${theme}`, async ({ page }) => {
        await page.setViewportSize(size)
        await openApp(page, { theme, path: p.path })
        await expect(page.getByRole('heading', { level: 1 })).toHaveText(p.heading)
        await expectNoAxeViolations(page)
        await expectNoSidewaysScroll(page)
      })
    }
  }

  test(`the degraded overview passes axe, phone, ${theme}`, async ({ page }) => {
    await page.setViewportSize(PHONE)
    await openApp(page, { theme, answers: { '/api/overview': { body: overviewDegraded() } } })
    await expect(page.locator('#nanoclaw-not-answering')).toContainText(
      'NanoClaw is not answering.',
    )
    await expect(page.locator('#page-sources')).toContainText('Some reads failed')
    await expectNoAxeViolations(page)
    await expectNoSidewaysScroll(page)
  })

  test(`the API error passes axe, ${theme}`, async ({ page }) => {
    await page.setViewportSize(PHONE)
    await openApp(page, { theme, answers: { '/api/overview': { status: 403 } } })
    await expect(page.locator('#page-banner')).toContainText('The console refused this browser')
    await expectNoAxeViolations(page)
  })
}
