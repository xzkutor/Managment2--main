/**
 * Vue Router instance for the SPA.
 *
 * History base: '/' (root, no prefix)
 *   Flask serves spa.html for all canonical operator routes AND for unknown
 *   non-/api/ paths (history-mode catch-all in ui_routes.py). Vue Router owns
 *   all client-side navigation; unknown paths render NotFoundPage.
 *
 * scrollBehavior: restores saved position on back/forward; scrolls to top for
 *   new navigation so each page starts at the top of the viewport.
 */
import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      // Restore position on browser back/forward
      return savedPosition
    }
    // Scroll to top on every new navigation
    return { top: 0, behavior: 'smooth' }
  },
})

export default router



