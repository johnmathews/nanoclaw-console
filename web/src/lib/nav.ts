/**
 * The pages in the header's navigation, in order. A route's `meta.nav` names the entry it
 * belongs to (router.ts), so a page below one (a task, a group) keeps its section marked.
 */
export type NavItem = { name: string; path: string; label: string }

export const NAV: NavItem[] = [
  { name: 'overview', path: '/', label: 'Overview' },
  { name: 'tasks', path: '/tasks', label: 'Tasks' },
  { name: 'groups', path: '/groups', label: 'Groups' },
  { name: 'permissions', path: '/permissions', label: 'Permissions' },
  { name: 'problems', path: '/problems', label: 'Problems' },
]
