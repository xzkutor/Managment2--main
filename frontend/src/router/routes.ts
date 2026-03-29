/**
 * SPA route definitions.
 *
 * Each route maps a canonical operator-facing path to a lazy-loaded
 * RouteView wrapper component. The wrapper renders the existing page
 * implementation; see frontend/src/pages/<page>/<Page>RouteView.vue.
 *
 * Flask serves spa.html for all known routes AND for unknown non-/api/ paths
 * (history-mode fallback in ui_routes.py). Vue Router owns client-side
 * navigation and renders NotFoundPage for unmatched paths.
 *
 * Route meta fields (title / subtitle) are consumed by AppShellHeader to
 * render the per-route header band without per-page shell duplication.
 */
import type { RouteRecordRaw } from 'vue-router'
// ---------------------------------------------------------------------------
// RouteMeta type augmentation
// ---------------------------------------------------------------------------
declare module 'vue-router' {
  interface RouteMeta {
    /** Page title displayed in the SPA shell header band. */
    title?: string
    /** Short descriptive subtitle displayed below the title. */
    subtitle?: string
  }
}
// ---------------------------------------------------------------------------
// Route table
// ---------------------------------------------------------------------------
export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'comparison',
    meta: {
      title: 'Pricewatch',
      subtitle: 'Порівняння асортименту між референсним та цільовим магазином.',
    },
    component: () => import('@/pages/comparison/ComparisonRouteView.vue'),
  },
  {
    path: '/service',
    name: 'service',
    meta: {
      title: 'Service Console',
      subtitle: 'Керування синхронізаціями, мапінгами та історією скрапінгу.',
    },
    component: () => import('@/pages/service/ServiceRouteView.vue'),
  },
  {
    path: '/gap',
    name: 'gap',
    meta: {
      title: '📋 Розрив асортименту',
      subtitle: 'Товари цільового магазину, які відсутні у референсному асортименті.',
    },
    component: () => import('@/pages/gap/GapRouteView.vue'),
  },
  {
    path: '/matches',
    name: 'matches',
    meta: {
      title: '✅ Підтверджені збіги',
      subtitle: 'Перегляд збережених маппінгів товарів.',
    },
    component: () => import('@/pages/matches/MatchesRouteView.vue'),
  },
  // ---------------------------------------------------------------------------
  // Catch-all — must be last; renders client-side 404 for unknown SPA paths.
  // Flask's history-mode fallback already serves spa.html for these URLs so
  // Vue Router receives the request and this route takes over.
  // ---------------------------------------------------------------------------
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/NotFoundPage.vue'),
  },
]
