// What the W9 pages show, in a real browser against the production build, at both widths:
// groups and channels, a group's page, permissions and problems; the links from a problem to
// what it is about; and the secret-absence check over every page.
import { expect, test } from '@playwright/test'
import {
  GROUP_IDS,
  PLANTED_MARK,
  STALE_APPROVAL_ID,
  TASKS,
  UNWIRED_CHANNEL_ID,
} from '../src/fixtures/api.ts'
import { DESKTOP, PHONE, openApp } from './support'

for (const [width, size] of [
  ['desktop', DESKTOP],
  ['phone', PHONE],
] as const) {
  test.describe(`at ${width} width`, () => {
    test.beforeEach(async ({ page }) => page.setViewportSize(size))

    test('the groups page answers first, then a card per group and the unwired channels', async ({
      page,
    }) => {
      await openApp(page, { theme: 'light', path: '/groups' })
      await expect(page.locator('#groups-answer')).toHaveText(
        'Three groups and five channels. Two channels are wired to no group. Two groups can write to files on the host.',
      )
      await expect(page.locator('#groups-list > li')).toHaveCount(3)
      await expect(page.locator(`#group-${GROUP_IDS.introspection}-mounts`)).toHaveText(
        '1 mount, read-write',
      )
      await expect(page.locator('#unwired-channels li')).toHaveCount(2)
      await expect(page.locator('#nav-groups')).toHaveAttribute('aria-current', 'page')
    })

    test('a group’s page shows channels, MCP hosts and read-write mounts', async ({ page }) => {
      await openApp(page, { theme: 'light', path: '/groups' })
      await page.locator(`#group-card-${GROUP_IDS.main} h3 a`).click()
      await expect(page).toHaveURL(`/groups/${GROUP_IDS.main}`)
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('main-group')
      await expect(page.locator('#group-model')).toHaveText('claude-opus-4-7')
      await expect(page.locator('#group-channels > ul > li')).toHaveCount(2)
      await expect(page.locator('#group-channel-mga-1779373703000-w1main-unknown')).toHaveText(
        'Dropped without a reply strict',
      )
      await expect(page.locator('#mcp-journal-where')).toHaveText('journal.example.internal:8443')
      await expect(page.locator('#mount-1')).toHaveAttribute('data-access', 'read-write')
      await expect(page.locator('#mount-1')).toContainText(
        'Read-write: the agent can change these files',
      )
      await expect(page.locator('#nav-groups')).toHaveAttribute('data-active', 'true')
    })

    test('the permissions page shows roles, the allowlist, the stale approval and what it cannot see', async ({
      page,
    }) => {
      await openApp(page, { theme: 'light', path: '/permissions' })
      await expect(page.locator('#permissions-answer')).toContainText('Two owners and one admin.')
      await expect(page.locator('#roles li')).toHaveCount(3)
      await expect(page.locator('#allowed-root-1')).toHaveAttribute('data-access', 'read-write')
      await expect(page.locator(`#approval-${STALE_APPROVAL_ID}`)).toHaveAttribute(
        'data-stale',
        'true',
      )
      await expect(page.locator('#not-visible li')).toHaveCount(3)
      await expect(page.locator('#not-visible')).toContainText('Egress lockdown')
    })

    test('the problems page lists every item and the host log groups', async ({ page }) => {
      await openApp(page, { theme: 'light', path: '/problems' })
      await expect(page.locator('#problems-answer')).toHaveText(
        'One error, six warnings and one note need a look.',
      )
      await expect(page.locator('#problems > ul > li')).toHaveCount(8)
      await expect(page.locator('#host-log-groups > li')).toHaveCount(4)
      await expect(page.locator('#log-group-0-sample')).toBeVisible()
    })
  })
}

test('a problem links to its task, its approval and its channel', async ({ page }) => {
  await openApp(page, { theme: 'light', path: '/problems' })
  await page.locator('#problems').getByRole('link', { name: 'See the approval' }).click()
  await expect(page).toHaveURL(`/permissions#approval-${STALE_APPROVAL_ID}`)
  await expect(page.locator(`#approval-${STALE_APPROVAL_ID}`)).toBeInViewport()

  await page.goto('/problems')
  await page.locator('#problems').getByRole('link', { name: 'See groups and channels' }).click()
  await expect(page).toHaveURL(`/groups#channel-${UNWIRED_CHANNEL_ID}`)
  await expect(page.locator(`#channel-${UNWIRED_CHANNEL_ID}`)).toBeInViewport()

  await page.goto('/problems')
  await page.locator('#problem-task_failures-3 a').click()
  await expect(page).toHaveURL(`/tasks/${TASKS[1]!.id}`)
})

test('the overview’s warnings link to the new pages', async ({ page }) => {
  await openApp(page, { theme: 'light' })
  await expect(
    page.locator('#warnings').getByRole('link', { name: 'See the approval' }),
  ).toHaveAttribute('href', `/permissions#approval-${STALE_APPROVAL_ID}`)
  await expect(
    page.locator('#warnings').getByRole('link', { name: 'See groups and channels' }),
  ).toHaveAttribute('href', `/groups#channel-${UNWIRED_CHANNEL_ID}`)
})

const ALL_PAGES = [
  '/',
  '/tasks',
  `/tasks/${TASKS[0]!.id}`,
  '/groups',
  ...Object.values(GROUP_IDS).map((id) => `/groups/${id}`),
  '/permissions',
  '/problems',
  '/audit',
]

test('no page carries the planted Bearer token anywhere in its DOM', async ({ page }) => {
  for (const path of ALL_PAGES) {
    await openApp(page, { theme: 'light', path })
    await expect(page.getByRole('heading', { level: 1 })).not.toHaveText('Page not found')
    await expect(page.locator('#page-freshness')).toBeVisible()
    const dom = await page.content()
    expect(dom, `${path} shows a planted secret`).not.toContain(PLANTED_MARK)
    expect(dom, `${path} shows a Bearer value`).not.toContain('Bearer ')
  }
})
