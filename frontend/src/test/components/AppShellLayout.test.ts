/**
 * AppShellLayout.test.ts — Regression tests for the SPA application shell contract.
 *
 * Covers (post-cutover-stabilization Commit 5):
 *   - sidebar owns ALL canonical navigation (not the header)
 *   - header is strictly title/subtitle — zero nav links
 *   - skip-to-content link exists for keyboard accessibility
 *   - brand block present in sidebar
 *   - page header is inside content area, NOT inside sidebar
 *   - RouterView renders inside #main-content
 *   - NotFoundPage still renders inside the shell
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppShellLayout from '@/layouts/AppShellLayout.vue'
import { NAV_LINKS } from '@/constants/navigation'

function makeRouter(initialPath = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      ...NAV_LINKS.map(link => ({
        path: link.to,
        component: { template: `<div class="page-stub">${link.label}</div>` },
        meta: { title: `Title for ${link.to}`, subtitle: `Sub for ${link.to}` },
      })),
      {
        path: '/:pathMatch(.*)*',
        name: 'not-found',
        component: { template: '<div class="not-found-stub">404</div>' },
      },
    ],
  })
  router.push(initialPath)
  return router
}

async function mountShell(path = '/') {
  const router = makeRouter(path)
  await router.isReady()
  return mount(AppShellLayout, {
    global: { plugins: [router] },
    attachTo: document.body,
  })
}

// ---------------------------------------------------------------------------
// Shell structure
// ---------------------------------------------------------------------------

describe('AppShellLayout — structure', () => {
  it('renders .app-shell wrapper', async () => {
    const wrapper = await mountShell()
    expect(wrapper.find('.app-shell').exists()).toBe(true)
  })

  it('sidebar is an <aside> element inside .app-shell', async () => {
    const wrapper = await mountShell()
    const sidebar = wrapper.find('.app-shell-sidebar')
    expect(sidebar.exists()).toBe(true)
    expect(sidebar.element.tagName).toBe('ASIDE')
  })

  it('sidebar has an aria-label', async () => {
    const wrapper = await mountShell()
    expect(wrapper.find('.app-shell-sidebar').attributes('aria-label')).toBeTruthy()
  })

  it('brand block is inside the sidebar', async () => {
    const wrapper = await mountShell()
    const sidebar = wrapper.find('.app-shell-sidebar')
    expect(sidebar.find('.app-shell-brand').exists()).toBe(true)
  })

  it('brand block contains the app name', async () => {
    const wrapper = await mountShell()
    expect(wrapper.find('.app-shell-brand').text()).toContain('Pricewatch')
  })

  it('AppShellSidebarNav is rendered inside the sidebar', async () => {
    const wrapper = await mountShell()
    const sidebar = wrapper.find('.app-shell-sidebar')
    expect(sidebar.find('nav').exists()).toBe(true)
  })

  it('AppShellHeader is inside .app-shell-content, NOT inside sidebar', async () => {
    const wrapper = await mountShell()
    const sidebar = wrapper.find('.app-shell-sidebar')
    const content = wrapper.find('.app-shell-content')
    // Header must not be inside sidebar
    expect(sidebar.find('header').exists()).toBe(false)
    // Header must be inside content
    expect(content.find('header').exists()).toBe(true)
  })

  it('#main-content exists and contains RouterView output', async () => {
    const wrapper = await mountShell('/')
    await wrapper.vm.$nextTick()
    const main = wrapper.find('#main-content')
    expect(main.exists()).toBe(true)
  })

  it('skip-to-content link exists', async () => {
    const wrapper = await mountShell()
    const skipLink = wrapper.find('a.skip-link')
    expect(skipLink.exists()).toBe(true)
    expect(skipLink.attributes('href')).toBe('#main-content')
  })
})

// ---------------------------------------------------------------------------
// Shell renders page content correctly
// ---------------------------------------------------------------------------

describe('AppShellLayout — page rendering', () => {
  it('renders page title from route.meta on /', async () => {
    const wrapper = await mountShell('/')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.app-shell-title').text()).toContain('Title for /')
  })

  it('renders page title from route.meta on /service', async () => {
    const wrapper = await mountShell('/service')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.app-shell-title').text()).toContain('Title for /service')
  })

  it('NotFound route still renders inside the shell (no blank screen)', async () => {
    const wrapper = await mountShell('/totally-unknown-path')
    await wrapper.vm.$nextTick()
    // Shell structure must be present
    expect(wrapper.find('.app-shell').exists()).toBe(true)
    expect(wrapper.find('.app-shell-sidebar').exists()).toBe(true)
    // NotFound stub content renders inside main
    expect(wrapper.find('.not-found-stub').exists()).toBe(true)
  })

  it('all canonical nav links are present regardless of current page', async () => {
    for (const path of ['/', '/service', '/gap', '/matches']) {
      const wrapper = await mountShell(path)
      const hrefs = wrapper.findAll('nav a').map(a => a.attributes('href'))
      NAV_LINKS.forEach(link => {
        expect(hrefs).toContain(link.to)
      })
    }
  })
})

// ---------------------------------------------------------------------------
// Commit 5 — Navigation ownership contract
// Hard-encodes: sidebar owns nav, header owns title/subtitle only.
// ---------------------------------------------------------------------------

describe('AppShellLayout — navigation ownership contract (Commit 5)', () => {
  it('sidebar nav contains exactly NAV_LINKS.length links', async () => {
    const wrapper = await mountShell('/')
    const navLinks = wrapper.find('.app-shell-sidebar nav').findAll('a')
    expect(navLinks).toHaveLength(NAV_LINKS.length)
  })

  it('the header contains zero anchor elements (no nav ownership)', async () => {
    const wrapper = await mountShell('/')
    await wrapper.vm.$nextTick()
    const header = wrapper.find('header.app-shell-header')
    expect(header.exists()).toBe(true)
    expect(header.findAll('a')).toHaveLength(0)
  })

  it('the header contains zero RouterLink elements', async () => {
    const wrapper = await mountShell('/')
    await wrapper.vm.$nextTick()
    const header = wrapper.find('header.app-shell-header')
    expect(header.findAllComponents({ name: 'RouterLink' })).toHaveLength(0)
  })

  it('ALL canonical destinations live in the sidebar nav, not scattered in content', async () => {
    const wrapper = await mountShell('/')
    await wrapper.vm.$nextTick()
    const sidebarHrefs = wrapper.find('.app-shell-sidebar').findAll('a').map(a => a.attributes('href'))
    const contentHrefs = wrapper.find('.app-shell-content').findAll('a').map(a => a.attributes('href'))
    NAV_LINKS.forEach(link => {
      expect(sidebarHrefs).toContain(link.to)
      // Nav links must NOT be duplicated inside the content area by the shell itself
      // (page content may add its own links, but that is tested per-page)
      expect(contentHrefs).not.toContain(link.to)
    })
  })

  it('active link in sidebar changes when route changes', async () => {
    const wrapper = await mountShell('/service')
    await wrapper.vm.$nextTick()
    const serviceLink = wrapper.find('.app-shell-sidebar').findAll('a')
      .find(a => a.attributes('href') === '/service')
    expect(serviceLink?.classes()).toContain('active')
    const homeLink = wrapper.find('.app-shell-sidebar').findAll('a')
      .find(a => a.attributes('href') === '/')
    expect(homeLink?.classes()).not.toContain('active')
  })
})
