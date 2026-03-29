/**
 * router.test.ts — SPA router contract tests.
 *
 * Verifies:
 * - each canonical route resolves to the expected named route
 * - unknown paths match the catch-all not-found route
 * - the catch-all does NOT intercept known canonical routes
 */
import { describe, it, expect } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routes } from '@/router/routes'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes,
  })
}

// ---------------------------------------------------------------------------
// Canonical routes resolve correctly
// ---------------------------------------------------------------------------

describe('router — canonical routes', () => {
  it('/ resolves to route name "comparison"', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('comparison')
  })

  it('/service resolves to route name "service"', async () => {
    const router = makeRouter()
    await router.push('/service')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('service')
  })

  it('/gap resolves to route name "gap"', async () => {
    const router = makeRouter()
    await router.push('/gap')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('gap')
  })

  it('/matches resolves to route name "matches"', async () => {
    const router = makeRouter()
    await router.push('/matches')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('matches')
  })
})

// ---------------------------------------------------------------------------
// Catch-all / NotFound behavior
// ---------------------------------------------------------------------------

describe('router — catch-all (NotFound)', () => {
  it('unknown path resolves to route name "not-found"', async () => {
    const router = makeRouter()
    await router.push('/this/does/not/exist')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('not-found')
  })

  it('deeply nested unknown path resolves to not-found', async () => {
    const router = makeRouter()
    await router.push('/a/b/c/d')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('not-found')
  })

  it('catch-all preserves the full unknown path', async () => {
    const router = makeRouter()
    await router.push('/unknown/page')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/unknown/page')
  })

  it('canonical routes are NOT matched by catch-all', async () => {
    const router = makeRouter()
    for (const path of ['/', '/service', '/gap', '/matches']) {
      await router.push(path)
      await router.isReady()
      expect(router.currentRoute.value.name).not.toBe('not-found')
    }
  })
})

// ---------------------------------------------------------------------------
// Route meta
// ---------------------------------------------------------------------------

describe('router — route meta', () => {
  it('/ has a title in meta', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.meta.title).toBeTruthy()
  })

  it('/service has a subtitle in meta', async () => {
    const router = makeRouter()
    await router.push('/service')
    await router.isReady()
    expect(router.currentRoute.value.meta.subtitle).toBeTruthy()
  })

  it('not-found route has no meta title (plain 404 screen)', async () => {
    const router = makeRouter()
    await router.push('/nonexistent')
    await router.isReady()
    expect(router.currentRoute.value.meta.title).toBeUndefined()
  })
})

