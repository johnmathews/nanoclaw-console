import type { PermissionsView, Role } from './types'
import { countWords, humanise } from './words'

/** A person by display name, else their id (`<channel>:<handle>`). */
export function personName(p: { user_name: string | null; user_id: string | null }): string {
  return p.user_name ?? p.user_id ?? 'Unknown user'
}

/** "Owner, everywhere", "Admin of server-bot". */
export function roleWords(r: Role): string {
  const role = r.role === null ? 'Unknown role' : humanise(r.role)
  if (r.scope === 'global' || !r.group) return `${role}, everywhere`
  return `${role} of ${r.group.name ?? r.group.id}`
}

/** The permissions page's answer line. */
export function permissionsAnswer(view: PermissionsView): string {
  const failed = view.sources.broker.errors
  const parts: string[] = []
  if (!view.roles.length && 'roles-list' in failed) parts.push('Couldn’t read the roles.')
  else {
    const owners = view.roles.filter((r) => r.role === 'owner').length
    const admins = view.roles.filter((r) => r.role === 'admin').length
    if (!owners && !admins) parts.push('No owners or admins.')
    else {
      const said = [owners && countWords(owners, 'owner'), admins && countWords(admins, 'admin')]
        .filter(Boolean)
        .map((s, i) => (i ? (s as string).toLowerCase() : s))
      parts.push(`${said.join(' and ')}.`)
    }
  }
  if (!view.members.length && 'members-list' in failed) parts.push('Couldn’t read the members.')
  else if (!view.members.length) parts.push('No group memberships.')
  else parts.push(`${countWords(view.members.length, 'group membership')}.`)
  const stale = view.approvals.filter((a) => a.stale).length
  if (stale)
    parts.push(
      `${countWords(stale, 'approval')} ${stale === 1 ? 'has' : 'have'} waited more than a week.`,
    )
  return parts.join(' ')
}
