// Release 2's confirmation dialogs (W15) in a real browser against the production build, /api
// mocked: each dialog at 1440 px and 390 px in both themes passes axe with the dialog open, does
// not scroll sideways, traps focus, starts on Cancel, closes on Escape with focus back on its
// button, and on confirm sends exactly one POST and shows the answer. No browser dialog appears.
//
// Set W15_SHOTS to a directory to save a screenshot of each dialog there.
import { expect, test, type Page } from '@playwright/test'
import { actionAnswer, GROUP_IDS, PAUSED_TASK, TASKS } from '../src/fixtures/api.ts'
import {
  DESKTOP,
  PHONE,
  THEMES,
  expectNoAxeViolations,
  expectNoSidewaysScroll,
  openApp,
  settle,
} from './support'

const PENDING = TASKS[0]!

const DIALOGS = [
  {
    name: 'resume of the overdue task',
    path: `/tasks/${PAUSED_TASK.id}`,
    button: '#action-toggle',
    post: `/api/tasks/${PAUSED_TASK.id}/resume`,
    answer: actionAnswer('resume'),
    title: 'Resume documentation-summary?',
    warning: 'runs once now',
    result: 'Resumed. It runs on its schedule again.',
  },
  {
    name: 'pause',
    path: `/tasks/${PENDING.id}`,
    button: '#action-toggle',
    post: `/api/tasks/${PENDING.id}/pause`,
    answer: actionAnswer('pause', 'already_in_state'),
    title: /^Pause /,
    warning: null,
    result: 'It was already paused, so nothing changed.',
  },
  {
    name: 'run',
    path: `/tasks/${PAUSED_TASK.id}`,
    button: '#action-run',
    post: `/api/tasks/${PAUSED_TASK.id}/run`,
    answer: actionAnswer('run'),
    title: 'Run documentation-summary now?',
    warning: 'spends tokens; it does not change the schedule',
    result: /^One run is queued/,
  },
  {
    name: 'restart',
    path: `/groups/${GROUP_IDS.main}`,
    button: '#action-restart',
    post: `/api/groups/${GROUP_IDS.main}/restart`,
    answer: actionAnswer('restart'),
    title: 'Restart main-group?',
    warning: 'interrupts a running turn',
    result: 'Restarted one container.',
  },
] as const

function noBrowserDialogs(page: Page): void {
  page.on('dialog', (d) => {
    throw new Error(`a browser ${d.type()} appeared: ${d.message()}`)
  })
}

for (const theme of THEMES) {
  for (const [width, size] of [
    ['desktop', DESKTOP],
    ['phone', PHONE],
  ] as const) {
    for (const d of DIALOGS) {
      test(`the ${d.name} dialog passes axe and traps focus, ${width}, ${theme}`, async ({
        page,
      }) => {
        noBrowserDialogs(page)
        await page.setViewportSize(size)
        await openApp(page, { theme, path: d.path })
        const opener = page.locator(d.button)
        await opener.click()
        const dialog = page.getByRole('alertdialog')
        await expect(dialog).toBeVisible()
        await settle(page)
        await expect(dialog.getByRole('heading', { level: 2 })).toHaveText(d.title)
        await expect(dialog).toHaveAccessibleName(d.title)
        await expect(dialog).toHaveAccessibleDescription(/^Now: /)
        if (d.warning) await expect(dialog.locator('#confirm-warning')).toContainText(d.warning)
        else await expect(dialog.locator('#confirm-warning')).toHaveCount(0)
        await expect(page.locator('#confirm-cancel')).toBeFocused()
        await expectNoAxeViolations(page)
        await expectNoSidewaysScroll(page)
        const shots = process.env.W15_SHOTS
        if (shots)
          await page.screenshot({
            path: `${shots}/dialog-${d.name.replace(/\W+/g, '-')}-${width}-${theme}.png`,
          })

        // The focus trap: Tab and Shift+Tab stay on the dialog's two buttons.
        await page.keyboard.press('Tab')
        await expect(page.locator('#confirm-act')).toBeFocused()
        await page.keyboard.press('Tab')
        await expect(page.locator('#confirm-cancel')).toBeFocused()
        await page.keyboard.press('Shift+Tab')
        await expect(page.locator('#confirm-act')).toBeFocused()

        await page.keyboard.press('Escape')
        await expect(dialog).toBeHidden()
        await expect(opener).toBeFocused()
      })
    }
  }
}

for (const d of DIALOGS) {
  test(`confirming the ${d.name} dialog sends one POST and says what happened`, async ({
    page,
  }) => {
    noBrowserDialogs(page)
    const sent: { url: string; headers: Record<string, string>; body: string | null }[] = []
    page.on('request', (r) => {
      if (r.method() === 'POST')
        sent.push({ url: new URL(r.url()).pathname, headers: r.headers(), body: r.postData() })
    })
    await openApp(page, {
      theme: 'light',
      path: d.path,
      answers: { [`POST ${d.post}`]: { body: d.answer } },
    })
    await page.locator(d.button).click()
    await page.locator('#confirm-act').click()
    await expect(page.getByRole('alertdialog')).toBeHidden()
    await expect(page.locator('#action-result')).toHaveText(d.result)
    expect(sent).toHaveLength(1)
    expect(sent[0]!.url).toBe(d.post)
    expect(sent[0]!.body).toBe('{}')
    expect(sent[0]!.headers['content-type']).toBe('application/json')
    expect(sent[0]!.headers['x-console-action']).toBe('1')
  })
}

test('a refused action keeps the dialog open with the reason, and passes axe', async ({ page }) => {
  const post = `/api/tasks/${PAUSED_TASK.id}/run`
  await page.setViewportSize(PHONE)
  await openApp(page, {
    theme: 'dark',
    path: `/tasks/${PAUSED_TASK.id}`,
    answers: { [`POST ${post}`]: { status: 503, body: actionAnswer('run', 'audit_unavailable') } },
  })
  await page.locator('#action-run').click()
  await page.locator('#confirm-act').click()
  await expect(page.locator('#confirm-error')).toHaveText(
    'The console can’t write its audit log, so it didn’t act. Nothing changed.',
  )
  await settle(page)
  await expectNoAxeViolations(page)
  await expectNoSidewaysScroll(page)
  const shots = process.env.W15_SHOTS
  if (shots) await page.screenshot({ path: `${shots}/dialog-refused-phone-dark.png` })
})

for (const [width, size] of [
  ['desktop', DESKTOP],
  ['phone', PHONE],
] as const) {
  test(`the task page's actions and the audit page, ${width}`, async ({ page }) => {
    await page.setViewportSize(size)
    const shots = process.env.W15_SHOTS
    await openApp(page, { theme: 'light', path: `/tasks/${PAUSED_TASK.id}` })
    await expect(page.locator('#action-toggle')).toHaveText('Resume')
    await expect(page.locator('#action-run')).toHaveText('Run now')
    await expectNoSidewaysScroll(page)
    if (shots) await page.screenshot({ path: `${shots}/task-page-${width}.png` })
    await openApp(page, { theme: 'light', path: '/audit' })
    await expect(page.locator('#audit-list > li')).toHaveCount(6)
    await expectNoSidewaysScroll(page)
    if (shots) await page.screenshot({ path: `${shots}/audit-page-${width}.png`, fullPage: true })
  })
}
