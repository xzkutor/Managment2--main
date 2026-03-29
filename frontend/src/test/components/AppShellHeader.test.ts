import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppShellHeader from '@/components/AppShellHeader.vue'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRouter(initialPath = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/',        component: {}, meta: { title: 'Pricewatch',            subtitle: 'Subtitle A' } },
      { path: '/service', component: {}, meta: { title: 'Service Console',       subtitle: 'Subtitle B' } },
      { path: '/gap',     component: {}, meta: { title: '📋 Розрив асортименту', subtitle: 'Subtitle C' } },
      { path: '/matches', component: {}, meta: { title: '✅ Підтверджені збіги', subtitle: 'Subtitle D' } },
    ],
  })
  router.push(initialPath)
  return router
}

async function mountHeader(path = '/') {
  const router = makeRouter(path)
  await router.isReady()
  return mount(AppShellHeader, { global: { plugins: [router] } })
}

// ---------------------------------------------------------------------------
// Structure — AppShellHeader is page-heading-only (no nav links)
// ---------------------------------------------------------------------------

describe('AppShellHeader — structure', () => {
  it('renders an <header> element with app-shell-header class', async () => {
    const wrapper = await mountHeader()
    expect(wrapper.find('header.app-shell-header').exists()).toBe(true)
  })

  it('does NOT render a nav element (nav ownership moved to AppShellSidebarNav)', async () => {
    const wrapper = await mountHeader()
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('does NOT render any RouterLink elements', async () => {
    const wrapper = await mountHeader()
    expect(wrapper.findAllComponents({ name: 'RouterLink' })).toHaveLength(0)
  })

  it('does NOT render any anchor elements', async () => {
    const wrapper = await mountHeader()
    expect(wrapper.findAll('a')).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// Title and subtitle from route meta
// ---------------------------------------------------------------------------

describe('AppShellHeader — route meta', () => {
  it('shows the title from route meta on /', async () => {
    const wrapper = await mountHeader('/')
    expect(wrapper.find('.app-shell-title').text()).toBe('Pricewatch')
  })

  it('shows the title from route meta on /service', async () => {
    const wrapper = await mountHeader('/service')
    expect(wrapper.find('.app-shell-title').text()).toBe('Service Console')
  })

  it('shows the subtitle from route meta', async () => {
    const wrapper = await mountHeader('/')
    expect(wrapper.find('.app-shell-subtitle').text()).toBe('Subtitle A')
  })

  it('shows correct subtitle for each route', async () => {
    for (const [path, expected] of [
      ['/service', 'Subtitle B'],
      ['/gap',     'Subtitle C'],
      ['/matches', 'Subtitle D'],
    ] as const) {
      const wrapper = await mountHeader(path)
      expect(wrapper.find('.app-shell-subtitle').text()).toBe(expected)
    }
  })

  it('falls back to "Pricewatch" when meta.title is absent', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: {} }],
    })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(AppShellHeader, { global: { plugins: [router] } })
    expect(wrapper.find('.app-shell-title').text()).toBe('Pricewatch')
  })

  it('omits subtitle element when meta.subtitle is absent', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: {}, meta: { title: 'No Subtitle' } }],
    })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(AppShellHeader, { global: { plugins: [router] } })
    expect(wrapper.find('.app-shell-subtitle').exists()).toBe(false)
  })
})
