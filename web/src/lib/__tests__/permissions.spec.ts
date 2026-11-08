import { describe, expect, it } from 'vitest'
import { permissionsView } from '../../fixtures/api'
import { permissionsAnswer, personName, roleWords } from '../permissions'
import type { PermissionsView } from '../types'

describe('people and roles in words', () => {
  it('names a person by display name, else id', () => {
    const [john, unnamed] = permissionsView().roles
    expect(personName(john!)).toBe('John')
    expect(personName(unnamed!)).toBe('whatsapp:31600000001')
    expect(personName({ user_name: null, user_id: null })).toBe('Unknown user')
  })

  it('says the role and where it applies', () => {
    const [john, , sara] = permissionsView().roles
    expect(roleWords(john!)).toBe('Owner, everywhere')
    expect(roleWords(sara!)).toBe('Admin of server-bot')
    expect(roleWords({ ...sara!, group: { id: 'ag-x', name: null } })).toBe('Admin of ag-x')
    expect(roleWords({ ...sara!, role: null, scope: 'global' })).toBe('Unknown role, everywhere')
    expect(roleWords({ ...sara!, role: 'super_user', scope: 'global' })).toBe(
      'Super user, everywhere',
    )
  })
})

describe('the permissions page’s answer line', () => {
  it('counts owners, admins and members, and the stale approvals', () => {
    expect(permissionsAnswer(permissionsView())).toBe(
      'Two owners and one admin. Two group memberships. One approval has waited more than a week.',
    )
  })

  it('handles none of anything', () => {
    const v: PermissionsView = { ...permissionsView(), roles: [], members: [], approvals: [] }
    expect(permissionsAnswer(v)).toBe('No owners or admins. No group memberships.')
  })

  it('does not claim none when roles or members could not be read', () => {
    const v: PermissionsView = {
      ...permissionsView(),
      roles: [],
      members: [],
      sources: {
        broker: { ok: false, errors: { 'roles-list': 'timeout', 'members-list': 'timeout' } },
      },
    }
    expect(permissionsAnswer(v)).toBe(
      'Couldn’t read the roles. Couldn’t read the members. One approval has waited more than a week.',
    )
  })

  it('words several stale approvals and one owner', () => {
    const v = permissionsView()
    v.roles = [v.roles[0]!]
    v.members = [v.members[0]!]
    v.approvals = [v.approvals[0]!, { ...v.approvals[0]!, id: 'appr-2' }]
    expect(permissionsAnswer(v)).toBe(
      'One owner. One group membership. Two approvals have waited more than a week.',
    )
  })
})
