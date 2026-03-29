import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppShellSidebarNav from '@/components/AppShellSidebarNav.vue'
import { NAV_LINKS } from '@/constants/navigation'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRouter(initialPath = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: NAV_LINKS.map(link => ({ path: link.to, component: {} })),
  })
  router.push(initialPath)
  return router
}

async function mountNav(path = '/') {
  const router = makeRouter(path)
  await router.isReady()
  return mount(AppShellSidebarNav, { global: { plugins: [router] } })
}

// ---------------------------------------------------------------------------
// Structure
// ---------------------------------------------------------------------------

describe('AppShellSidebarNav — structure', () => {
  it('renders a <nav> element', async () => {
    const wrapper = await mountNav()
    expect(wrapper.find('nav').exists()).toBe(true)
  })

  it('has aria-label on the nav element', async () => {
    const wrapper = await mountNav()
    expect(wrapper.find('nav').attributes('aria-label')).toBeTruthy()
  })

  it('renders exactly four navigation links', async () => {
    const wrapper = await mountNav()
    const links = wrapper.findAllComponents({ name: 'RouterLink' })
    expect(links).toHaveLength(NAV_LINKS.length)
    expect(links).toHaveLength(4)
  })

  it('every link has app-shell-sidebar-link class', async () => {
    const wrapper = await mountNav()
    wrapper.findAll('a').forEach(link => {
      expect(link.classes()).toContain('app-shell-sidebar-link')
    })
  })
})

// ---------------------------------------------------------------------------
// Link destinations — sourced from shared NAV_LINKS constant
// ---------------------------------------------------------------------------

describe('AppShellSidebarNav — link destinations', () => {
  it('contains a link to /', async () => {
    const wrapper = await mountNav()
    const hrefs = wrapper.findAll('a').map(a => a.attributes('href'))
    expect(hrefs).toContain('/')
  })

  it('contains a link to /service', async () => {
    const wrapper = await mountNav()
    const hrefs = wrapper.findAll('a').map(a => a.attributes('href'))
    expect(hrefs).toContain('/service')
  })

  it('contains a link to /gap', async () => {
    const wrapper = await mountNav()
    const hrefs = wrapper.findAll('a').map(a => a.attributes('href'))
    expect(hrefs).toContain('/gap')
  })

  it('contains a link to /matches', async () => {
    const wrapper = await mountNav()
    const hrefs = wrapper.findAll('a').map(a => a.attributes('href'))
    expect(hrefs).toContain('/matches')
  })

  it('link hrefs match NAV_LINKS constant exactly', async () => {
    const wrapper = await mountNav()
    const hrefs = wrapper.findAll('a').map(a => a.attributes('href'))
    NAV_LINKS.forEach(link => {
      expect(hrefs).toContain(link.to)
    })
  })
})

// ---------------------------------------------------------------------------
// Active route semantics
// ---------------------------------------------------------------------------

describe('AppShellSidebarNav — active route', () => {
  it('sets aria-current="page" on the exactly-active link', async () => {
    const wrapper = await mountNav('/service')
    const serviceLink = wrapper.findAll('a').find(a => a.attributes('href') === '/service')
    expect(serviceLink?.attributes('aria-current')).toBe('page')
  })

  it('does NOT set aria-current on inactive links', async () => {
    const wrapper = await mountNav('/service')
    const otherLinks = wrapper.findAll('a').filter(a => a.attributes('href') !== '/service')
    otherLinks.forEach(link => {
      expect(link.attributes('aria-current')).toBeUndefined()
    })
  })

  it('does NOT mark "/" as active when on /gap (prefix-match suppressed)', async () => {
    const wrapper = await mountNav('/gap')
    const homeLink = wrapper.findAll('a').find(a => a.attributes('href') === '/')
    // exact-active-class only — "/" should not be "active" when on /gap
    expect(homeLink?.attributes('aria-current')).toBeUndefined()
  })

  it('marks "/" as active only when exactly on /', async () => {
    const wrapper = await mountNav('/')
    const homeLink = wrapper.findAll('a').find(a => a.attributes('href') === '/')
    expect(homeLink?.attributes('aria-current')).toBe('page')
  })
})

// ---------------------------------------------------------------------------
// Commit 7 — Accessibility hardening
// ---------------------------------------------------------------------------

describe('AppShellSidebarNav — accessibility (Commit 7)', () => {
  it('the nav element has an aria-label for screen readers', async () => {
    const wrapper = await mountNav()
    const nav = wrapper.find('nav')
    expect(nav.attributes('aria-label')).toBeTruthy()
  })

  it('active link has "active" class for visual indication', async () => {
    const wrapper = await mountNav('/service')
    const serviceLink = wrapper.findAll('a').find(a => a.attributes('href') === '/service')
    expect(serviceLink?.classes()).toContain('active')
  })

  it('inactive links do NOT have "active" class', async () => {
    const wrapper = await mountNav('/service')
    const others = wrapper.findAll('a').filter(a => a.attributes('href') !== '/service')
    others.forEach(link => {
      expect(link.classes()).not.toContain('active')
    })
  })

  it('every link has app-shell-sidebar-link class (CSS focus/active styles apply)', async () => {
    const wrapper = await mountNav()
    wrapper.findAll('a').forEach(a => {
      expect(a.classes()).toContain('app-shell-sidebar-link')
    })
  })
})
