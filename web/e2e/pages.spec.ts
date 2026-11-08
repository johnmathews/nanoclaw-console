// What each page shows, in a real browser against the production build, at both widths: the
// W8 acceptance checks (the paused documentation summary's warning, the table becoming cards on
// a phone, the navigation) and the API's degraded answers.
import { expect, test } from '@playwright/test'
import { PAUSED_TASK, overview } from '../src/fixtures/api.ts'
import { DESKTOP, PHONE, openApp } from './support'

const OVERDUE = 'Paused — will run once immediately if resumed'

for (const [width, size] of [
  ['desktop', DESKTOP],
  ['phone', PHONE],
] as const) {
  test.describe(`at ${width} width`, () => {
    test.beforeEach(async ({ page }) => page.setViewportSize(size))

    test('the overview answers first, then shows Claude, NanoClaw, the quota and the counts', async ({
      page,
    }) => {
      await openApp(page, { theme: 'light' })
      await expect(page.locator('#overview-answer')).toHaveText(
        'Claude is answering NanoClaw’s agents. NanoClaw is running.',
      )
      await expect(page.locator('#claude-status')).toHaveAttribute('data-status', 'ok')
      await expect(page.locator('#claude-status')).toHaveText('OK')
      await expect(page.locator('#quota-label')).toHaveText(overview().quota.label)
      await expect(page.locator('#nanoclaw-channels li')).toHaveCount(2)
      await expect(page.locator('#warnings li')).toHaveCount(4)
      await expect(page.locator('#page-freshness')).toContainText('Refreshes every 30 seconds.')
    })

    test('the paused documentation summary warns that it runs at once if resumed', async ({
      page,
    }) => {
      await openApp(page, { theme: 'light', path: '/tasks' })
      const shown =
        width === 'desktop'
          ? page.locator(`#task-row-${PAUSED_TASK.id}`)
          : page.locator(`#task-card-${PAUSED_TASK.id}`)
      await expect(shown).toBeVisible()
      await expect(shown).toContainText(OVERDUE)
      await expect(shown.getByRole('link', { name: 'documentation-summary' })).toBeVisible()
      // One layout at a time: the table on a desktop, the cards on a phone.
      await expect(page.locator('#tasks-table')).toBeVisible({ visible: width === 'desktop' })
      await expect(page.locator('#tasks-cards')).toBeVisible({ visible: width === 'phone' })
    })

    test('a task’s page shows what it will do, its prompt and the warning', async ({ page }) => {
      await openApp(page, { theme: 'light', path: '/tasks' })
      const scope = width === 'desktop' ? '#tasks-table' : '#tasks-cards'
      await page.locator(scope).getByRole('link', { name: 'documentation-summary' }).click()
      await expect(page).toHaveURL(`/tasks/${PAUSED_TASK.id}`)
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('documentation-summary')
      await expect(page.locator('#task-overdue')).toContainText(OVERDUE)
      await expect(page.locator('#task-file-content h3')).toHaveText('Documentation summary')
      await expect(page.locator('#task-prompt')).toHaveText(PAUSED_TASK.prompt!)
      // The planted script, image and javascript: link in the task file never reach the page.
      expect(await page.locator('#task-file-content script, #task-file-content img').count()).toBe(
        0,
      )
      expect(await page.locator('#task-file-content a[href^="javascript:"]').count()).toBe(0)
      await expect(page.locator('#nav-tasks')).toHaveAttribute('data-active', 'true')
    })
  })
}

test('the header links each page and marks the current one', async ({ page }) => {
  await openApp(page, { theme: 'light' })
  await expect(page.locator('#nav-overview')).toHaveAttribute('aria-current', 'page')
  await page.locator('#nav-tasks').click()
  await expect(page).toHaveURL('/tasks')
  await expect(page.locator('#nav-tasks')).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveTitle('Scheduled tasks · NanoClaw console')
})

test('the task page says when the broker cannot answer', async ({ page }) => {
  await openApp(page, {
    theme: 'light',
    path: '/tasks/task-x',
    answers: { '/api/tasks/task-x': { status: 503, body: { error: 'broker_unavailable' } } },
  })
  await expect(page.locator('#page-banner')).toContainText('Couldn’t reach the broker')
})

test('the page refreshes through the backend every 30 seconds', async ({ page }) => {
  await page.clock.install()
  let calls = 0
  await page.route('**/api/overview', async (route) => {
    calls += 1
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(overview()) })
  })
  await page.goto('/')
  await expect(page.locator('#overview-answer')).toBeVisible()
  expect(calls).toBe(1)
  await page.clock.runFor(30_000)
  await expect.poll(() => calls).toBe(2)
})
