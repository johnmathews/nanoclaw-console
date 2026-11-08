import { createRouter, type RouterHistory } from 'vue-router'
import OverviewPage from './views/OverviewPage.vue'
import TasksPage from './views/TasksPage.vue'
import TaskPage from './views/TaskPage.vue'
import NotFoundPage from './views/NotFoundPage.vue'

/**
 * The client routes. The API serves index.html for any path it does not own (architecture.md
 * §4.7), so these are real paths, not hashes. `meta.nav` names the header entry a page belongs
 * to, so a task's page keeps Tasks marked.
 */
export function createAppRouter(history: RouterHistory) {
  return createRouter({
    history,
    routes: [
      { path: '/', name: 'overview', component: OverviewPage, meta: { nav: 'overview' } },
      { path: '/tasks', name: 'tasks', component: TasksPage, meta: { nav: 'tasks' } },
      { path: '/tasks/:id', name: 'task', component: TaskPage, meta: { nav: 'tasks' } },
      { path: '/:rest(.*)*', name: 'not-found', component: NotFoundPage },
    ],
    scrollBehavior: () => ({ top: 0 }),
  })
}
