import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GROUP_IDS, permissionsView, STALE_APPROVAL_ID } from '../../fixtures/api'
import { mountApp, text, useClock } from '../../__tests__/mountApp'
import type { PermissionsView } from '../../lib/types'

async function open(body: unknown = permissionsView()) {
  return mountApp('/permissions', { '/api/permissions': body })
}

describe('the permissions page', () => {
  beforeEach(useClock)
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('answers first', async () => {
    const wrapper = await open()
    expect(text(wrapper, 'h1')).toBe('Permissions')
    expect(text(wrapper, '#permissions-answer')).toBe(
      'Two owners and one admin. Two group memberships. One approval has waited more than a week.',
    )
  })

  it('lists owners and admins with where their role applies', async () => {
    const wrapper = await open()
    expect(wrapper.findAll('#roles li')).toHaveLength(3)
    expect(text(wrapper, '#role-0')).toContain('John')
    expect(text(wrapper, '#role-0')).toContain('Owner, everywhere')
    expect(text(wrapper, '#role-0')).toContain('slack:U07JOHN0001')
    expect(text(wrapper, '#role-2')).toContain('Admin of server-bot')
    expect(wrapper.find('#role-2 a').attributes('href')).toBe(`/groups/${GROUP_IDS.server}`)
    expect(text(wrapper, '#role-2')).toContain('granted by slack:U07JOHN0001')
  })

  it('lists members and the group each belongs to', async () => {
    const wrapper = await open()
    expect(text(wrapper, '#member-0')).toContain('Sara')
    expect(text(wrapper, '#member-0')).toContain('Member of server-bot')
    expect(text(wrapper, '#member-1')).toContain('Member of ag-1779999999999-gone00')
    expect(wrapper.find('#member-1 a').exists()).toBe(false)
  })

  it('counts agent-to-agent policies without showing their unshaped fields', async () => {
    const wrapper = await open()
    expect(text(wrapper, '#policies-summary')).toBe(
      'One policy. The console doesn’t show its fields yet; ncl policies list does.',
    )
    const none = permissionsView()
    none.policies = []
    wrapper.unmount()
    document.body.innerHTML = ''
    const w2 = await open(none)
    expect(text(w2, '#policies-summary')).toBe('No agent-to-agent policies.')
  })

  it('says who may message whom', async () => {
    const wrapper = await open()
    expect(wrapper.findAll('#destinations li')).toHaveLength(3)
    expect(text(wrapper, '#perm-destination-0')).toBe(
      'main-group may message #server (a slack channel) as server',
    )
    expect(text(wrapper, '#perm-destination-2')).toBe(
      'ag-1779999999999-gone00 may message mg-1779000000000-old000 (a slack channel) as old',
    )
  })

  it('shows the mount allowlist, read-write roots flagged', async () => {
    const wrapper = await open()
    const roots = wrapper.findAll('#mount-allowlist li[data-access]')
    expect(roots.map((r) => r.attributes('data-access'))).toEqual([
      'read-only',
      'read-write',
      'read-only',
    ])
    expect(text(wrapper, '#allowed-root-1')).toContain('/srv/apps/nanoclaw')
    expect(text(wrapper, '#allowed-root-1')).toContain('Read-write allowed')
    expect(text(wrapper, '#blocked-patterns')).toBe('.ssh .env credentials')
    expect(text(wrapper, '#non-main-read-only')).toBe(
      'Groups other than main get read-only mounts, whatever a root allows.',
    )
  })

  it('says when the allowlist could not be read, and why', async () => {
    const body: PermissionsView = {
      ...permissionsView(),
      mount_allowlist: { available: false, reason: 'not_readable' },
    }
    const wrapper = await open(body)
    expect(text(wrapper, '#mount-allowlist')).toContain(
      'The broker couldn’t read the allowlist file on the host.',
    )
    wrapper.unmount()
    document.body.innerHTML = ''
    const w2 = await open({
      ...permissionsView(),
      mount_allowlist: { available: false, reason: 'broker_error' },
    })
    expect(text(w2, '#mount-allowlist')).toContain('Couldn’t read the mount allowlist.')
  })

  it('flags a stale approval and says it never expires', async () => {
    const wrapper = await open()
    const stale = wrapper.find(`#approval-${STALE_APPROVAL_ID}`)
    expect(stale.attributes('data-stale')).toBe('true')
    expect(text(wrapper, `#approval-${STALE_APPROVAL_ID}`)).toContain('Change main-group config')
    expect(text(wrapper, `#approval-${STALE_APPROVAL_ID}`)).toContain(
      'Waiting 147 days, and it never expires.',
    )
    const fresh = wrapper.find('#approval-appr-1786540000000-fr3sh0')
    expect(fresh.attributes('data-stale')).toBe('false')
    expect(fresh.text()).toContain('Expires tomorrow at 13:00 CET')
  })

  it('names what the console cannot see, with why', async () => {
    const wrapper = await open()
    const items = wrapper.findAll('#not-visible li')
    expect(items).toHaveLength(3)
    expect(text(wrapper, '#not-visible-0')).toContain('Per-group environment variables')
    expect(text(wrapper, '#not-visible-1')).toContain('OneCLI secret assignments')
    expect(text(wrapper, '#not-visible-2')).toContain('Egress lockdown')
    expect(text(wrapper, '#not-visible-2')).toContain('the broker has neither the Docker socket')
  })

  it('says none for empty lists, and couldn’t read for failed ones', async () => {
    const body: PermissionsView = {
      ...permissionsView(),
      roles: [],
      members: [],
      destinations: [],
      approvals: [],
      sources: { broker: { ok: false, errors: { 'roles-list': 'timeout' } } },
    }
    const wrapper = await open(body)
    expect(text(wrapper, '#roles')).toContain('Couldn’t read the roles.')
    expect(text(wrapper, '#members')).toContain('No group memberships.')
    expect(text(wrapper, '#destinations')).toContain('No destinations.')
    expect(text(wrapper, '#approvals')).toContain('No approvals are waiting.')
  })

  it('scrolls to the approval a link names', async () => {
    const scroll = vi.fn<() => void>()
    const before = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scroll
    try {
      const wrapper = await mountApp(`/permissions#approval-${STALE_APPROVAL_ID}`, {
        '/api/permissions': permissionsView(),
      })
      expect(wrapper.find(`#approval-${STALE_APPROVAL_ID}`).exists()).toBe(true)
      expect(scroll).toHaveBeenCalledTimes(1)
      expect(scroll.mock.contexts[0]).toBe(document.getElementById(`approval-${STALE_APPROVAL_ID}`))
    } finally {
      Element.prototype.scrollIntoView = before
    }
  })
})
