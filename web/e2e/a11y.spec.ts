// Accessibility gate (from the design-system skill's a11y.spec.ts, by way of tracker): axe (WCAG
// 2.2 A and AA, and its best practices) on the app in both themes at desktop and phone width, with
// /api mocked; and the page's own words for each answer the API can give.
//
// The theme is the app's `.dark` class on <html>, which tokens.css's dark block matches
// (`npm run tokens` passes --dark-selector .dark). The first test fails if switching it changes
// nothing, so a "dark" audit can never quietly re-run light.
import { expect, test } from '@playwright/test'
import {
  DESKTOP,
  PHONE,
  THEMES,
  canvasToken,
  expectNoAxeViolations,
  expectNoSidewaysScroll,
  openApp,
} from './support'

test('dark really is dark', async ({ page, context }) => {
  await openApp(page, { theme: 'light' })
  const light = await canvasToken(page)
  const dark = await context.newPage()
  await openApp(dark, { theme: 'dark' })
  expect(await dark.evaluate(() => document.documentElement.classList.contains('dark'))).toBe(true)
  expect(await canvasToken(dark), '--canvas is identical in both themes').not.toBe(light)
})

for (const theme of THEMES) {
  for (const [name, size] of [
    ['desktop', DESKTOP],
    ['phone', PHONE],
  ] as const) {
    test(`the page passes axe, ${name}, ${theme}`, async ({ page }) => {
      await page.setViewportSize(size)
      await openApp(page, { theme })
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('NanoClaw console')
      await expect(page.getByTestId('api-status')).toContainText('The console’s API answered')
      await expectNoAxeViolations(page)
      await expectNoSidewaysScroll(page)
    })
  }

  test(`the API error passes axe, ${theme}`, async ({ page }) => {
    await page.setViewportSize(PHONE)
    await openApp(page, { theme, status: 403, body: { detail: 'Forbidden' } })
    await expect(page.getByRole('alert')).toContainText('Couldn’t reach the console’s API')
    await expectNoAxeViolations(page)
  })
}
