/**
 * The pages in the header's navigation, in order. W9 adds Groups, Permissions and Problems here
 * (and their routes in router.ts); nothing else in the shell changes.
 */
export type NavItem = { name: string; path: string; label: string }

export const NAV: NavItem[] = [
  { name: 'overview', path: '/', label: 'Overview' },
  { name: 'tasks', path: '/tasks', label: 'Tasks' },
]
