import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotFoundPage from '@/pages/NotFoundPage.vue'

/** Build a minimal router so RouterLink inside NotFoundPage resolves. */
function makeRouter(currentPath = '/some/unknown/path') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: {} },
      { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundPage },
    ],
  })
  router.push(currentPath)
  return router
}

async function mountNotFound(path = '/some/unknown/path') {
  const router = makeRouter(path)
  await router.isReady()
  return mount(NotFoundPage, {
    global: { plugins: [router] },
  })
}

// ---------------------------------------------------------------------------
// Structure
// ---------------------------------------------------------------------------

describe('NotFoundPage — structure', () => {
  it('renders a 404 code', async () => {
    const wrapper = await mountNotFound()
    expect(wrapper.find('.not-found__code').text()).toBe('404')
  })

  it('renders a title', async () => {
    const wrapper = await mountNotFound()
    expect(wrapper.find('.not-found__title').exists()).toBe(true)
    expect(wrapper.find('.not-found__title').text()).toBeTruthy()
  })

  it('renders a home link pointing to /', async () => {
    const wrapper = await mountNotFound()
    const homeLink = wrapper.find('.not-found__home-link')
    expect(homeLink.exists()).toBe(true)
    expect(homeLink.attributes('href')).toBe('/')
  })
})

// ---------------------------------------------------------------------------
// Path display
// ---------------------------------------------------------------------------

describe('NotFoundPage — path display', () => {
  it('shows the current unknown path in the message', async () => {
    const wrapper = await mountNotFound('/does/not/exist')
    expect(wrapper.find('.not-found__path').text()).toBe('/does/not/exist')
  })

  it('shows a different path when navigated to a different unknown route', async () => {
    const wrapper = await mountNotFound('/admin/missing')
    expect(wrapper.find('.not-found__path').text()).toBe('/admin/missing')
  })
})

