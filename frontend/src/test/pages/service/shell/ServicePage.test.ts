/**
 * ServicePage.test.ts — tests for the route-addressable service console shell.
 *
 * After service-console-redesign the service page is route-driven:
 *  - SERVICE_SECTIONS from useServiceSections describes sections by routeName
 *  - /service redirects to /service/categories
 *  - ServiceRouteView renders the left section rail + <RouterView>
 *  - Each section is lazy-loaded via its own child route (no v-show persistence)
 */
import { describe, it, expect, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory, RouterView } from 'vue-router'
import { routes } from '@/router/routes'
import { SERVICE_SECTIONS } from '@/pages/service/composables/useServiceSections'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

// ---------------------------------------------------------------------------
// useServiceSections — section descriptor contract
// ---------------------------------------------------------------------------

describe('useServiceSections — SERVICE_SECTIONS', () => {
  it('has exactly 4 sections', () => {
    expect(SERVICE_SECTIONS).toHaveLength(4)
  })

  it('contains categories, mappings, scheduler, history', () => {
    const ids = SERVICE_SECTIONS.map((s) => s.id)
    expect(ids).toContain('categories')
    expect(ids).toContain('mappings')
    expect(ids).toContain('scheduler')
    expect(ids).toContain('history')
  })

  it('each section has a routeName starting with "service-"', () => {
    for (const s of SERVICE_SECTIONS) {
      expect(s.routeName).toMatch(/^service-/)
    }
  })

  it('each section has non-empty id, label, icon, routeName', () => {
    for (const s of SERVICE_SECTIONS) {
      expect(s.id).toBeTruthy()
      expect(s.label).toBeTruthy()
      expect(s.icon).toBeTruthy()
      expect(s.routeName).toBeTruthy()
    }
  })
})

// ---------------------------------------------------------------------------
// Router — /service section route contract
// ---------------------------------------------------------------------------

describe('ServiceRouteView — route navigation', () => {
  it('/service redirects to /service/categories', async () => {
    const router = makeRouter()
    await router.push('/service')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/service/categories')
    expect(router.currentRoute.value.name).toBe('service-categories')
  })

  it('/service/categories resolves directly', async () => {
    const router = makeRouter()
    await router.push('/service/categories')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('service-categories')
  })

  it('/service/mappings resolves directly', async () => {
    const router = makeRouter()
    await router.push('/service/mappings')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('service-mappings')
  })

  it('/service/scheduler resolves directly', async () => {
    const router = makeRouter()
    await router.push('/service/scheduler')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('service-scheduler')
  })

  it('/service/history resolves directly', async () => {
    const router = makeRouter()
    await router.push('/service/history')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('service-history')
  })

  it('all service section routes are not matched by catch-all', async () => {
    const router = makeRouter()
    for (const s of SERVICE_SECTIONS) {
      await router.push({ name: s.routeName })
      await router.isReady()
      expect(router.currentRoute.value.name).not.toBe('not-found')
    }
  })

  it('service section route inherits service console meta title', async () => {
    const router = makeRouter()
    await router.push('/service/categories')
    await router.isReady()
    expect(router.currentRoute.value.meta.title).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// ServiceRouteView — shell rendering
// ---------------------------------------------------------------------------

// Stub all section components so the shell can mount without their dependencies
vi.mock('@/pages/service/categories/ServiceCategoriesTab.vue', () => ({
  default: { template: '<div data-testid="categories-section">categories</div>' },
}))
vi.mock('@/pages/service/mappings/MappingsTab.vue', () => ({
  default: { template: '<div data-testid="mappings-section">mappings</div>' },
}))
vi.mock('@/pages/service/scheduler/SchedulerApp.vue', () => ({
  default: { template: '<div data-testid="scheduler-section">scheduler</div>' },
}))
vi.mock('@/pages/service/history/ServiceHistoryApp.vue', () => ({
  default: { template: '<div data-testid="history-section">history</div>' },
}))


/** Thin wrapper so the inner RouterView in ServiceRouteView gets correct depth. */
const AppShell = defineComponent({ template: '<RouterView />', components: { RouterView } })

describe('ServiceRouteView — shell structure', () => {
  async function mountShell(path = '/service/categories') {
    const router = makeRouter()
    await router.push(path)
    await router.isReady()
    return mount(AppShell, { global: { plugins: [router] } })
  }

  it('renders the left section rail (.sc-rail)', async () => {
    const w = await mountShell()
    expect(w.find('.sc-rail').exists()).toBe(true)
  })

  it('renders the right workspace (.sc-workspace-main)', async () => {
    const w = await mountShell()
    expect(w.find('.sc-workspace-main').exists()).toBe(true)
  })

  it('renders a nav link for each section', async () => {
    const w = await mountShell()
    const links = w.findAll('.sc-rail-item')
    expect(links).toHaveLength(SERVICE_SECTIONS.length)
  })

  it('section rail labels match SERVICE_SECTIONS', async () => {
    const w = await mountShell()
    const linkTexts = w.findAll('.sc-rail-item').map((l) => l.text())
    for (const s of SERVICE_SECTIONS) {
      expect(linkTexts.some((t) => t.includes(s.label))).toBe(true)
    }
  })

  it('active link gets sc-rail-item--active class for current route', async () => {
    const w = await mountShell('/service/categories')
    // RouterLink adds active-class when to.name matches current route
    const activeLinks = w.findAll('.sc-rail-item--active')
    expect(activeLinks.length).toBeGreaterThanOrEqual(1)
  })

  it('section workspace mounts the active section component', async () => {
    const w = await mountShell('/service/categories')
    expect(w.find('[data-testid="categories-section"]').exists()).toBe(true)
  })

  it('inactive sections are NOT mounted (route-driven, not v-show)', async () => {
    const w = await mountShell('/service/categories')
    expect(w.find('[data-testid="mappings-section"]').exists()).toBe(false)
    expect(w.find('[data-testid="scheduler-section"]').exists()).toBe(false)
    expect(w.find('[data-testid="history-section"]').exists()).toBe(false)
  })
})
