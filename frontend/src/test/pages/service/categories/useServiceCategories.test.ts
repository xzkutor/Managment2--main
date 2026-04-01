import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { useServiceCategories } from '@/pages/service/categories/composables/useServiceCategories'

// ---------------------------------------------------------------------------
// Mock API client
// ---------------------------------------------------------------------------

vi.mock('@/api/client', () => ({
  fetchStores: vi.fn(),
  syncAdminStores: vi.fn(),
  fetchCategoriesForStore: vi.fn(),
  syncStoreCategories: vi.fn(),
  syncCategoryProducts: vi.fn(),
  fetchScrapeStatus: vi.fn(),
}))

import * as client from '@/api/client'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const stores = [
  { id: 1, name: 'prohockey', is_reference: true, base_url: null },
  { id: 2, name: 'hockeyworld', is_reference: false, base_url: null },
]

const categories = [
  { id: 10, store_id: 1, name: 'Ковзани', normalized_name: 'kovzany', url: 'http://a.com', external_id: null, updated_at: '2026-01-01T00:00:00Z', product_count: 5 },
  { id: 11, store_id: 1, name: 'Шоломи', normalized_name: 'sholomy', url: null, external_id: null, updated_at: null, product_count: 0 },
]

const scrapeRuns = [
  {
    id: 1, store_id: 1, store: { id: 1, name: 'prohockey', is_reference: true, base_url: null },
    job_id: null, run_type: 'store_category_sync', trigger_type: 'manual', status: 'running',
    attempt: 1, queued_at: null, started_at: '2026-01-01T12:00:00Z', finished_at: null,
    worker_id: null, categories_processed: null, products_processed: null,
    products_created: null, products_updated: null, price_changes_detected: null,
    error_message: null, metadata_json: null, checkpoint_out_json: null,
    retryable: false, retry_of_run_id: null, retry_processed: false, retry_exhausted: false,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  // Reset both config globals to avoid test pollution.
  delete window.__PRICEWATCH_BOOTSTRAP__
  // Legacy SERVICE_CONFIG default (fallback path tested separately below)
  ;(window as Window & { SERVICE_CONFIG?: unknown }).SERVICE_CONFIG = { enableAdminSync: false }
  vi.mocked(client.fetchStores).mockResolvedValue(stores)
  vi.mocked(client.fetchScrapeStatus).mockResolvedValue(scrapeRuns)
  vi.mocked(client.fetchCategoriesForStore).mockResolvedValue([])
  vi.mocked(client.syncStoreCategories).mockResolvedValue(categories)
  vi.mocked(client.syncCategoryProducts).mockResolvedValue({
    products_processed: 10, products_created: 2, products_updated: 3, price_changes_detected: 1,
  })
})

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe('useServiceCategories — initial state', () => {
  it('loads stores and scrape status on mount', async () => {
    const state = useServiceCategories()
    await flushPromises()

    expect(state.stores.value).toHaveLength(2)
    expect(state.scrapeRuns.value).toHaveLength(1)
    expect(client.fetchStores).toHaveBeenCalledTimes(1)
    expect(client.fetchScrapeStatus).toHaveBeenCalledTimes(1)
  })

  it('starts with no store selected in the workspace pane', () => {
    const state = useServiceCategories()
    expect(state.targetPane.storeId.value).toBeNull()
  })

  it('does not expose refPane (single-workspace model)', () => {
    const state = useServiceCategories()
    expect((state as unknown as Record<string, unknown>).refPane).toBeUndefined()
  })

  it('enableAdminSync reads window.__PRICEWATCH_BOOTSTRAP__ (canonical format)', () => {
    window.__PRICEWATCH_BOOTSTRAP__ = { enableAdminSync: true }
    const state = useServiceCategories()
    expect(state.enableAdminSync.value).toBe(true)
  })

  it('enableAdminSync falls back to window.SERVICE_CONFIG when bootstrap absent', () => {
    // __PRICEWATCH_BOOTSTRAP__ is deleted in beforeEach; only SERVICE_CONFIG is set
    ;(window as Window & { SERVICE_CONFIG?: unknown }).SERVICE_CONFIG = { enableAdminSync: true }
    const state = useServiceCategories()
    expect(state.enableAdminSync.value).toBe(true)
  })

  it('enableAdminSync is false when both config globals are absent', () => {
    delete (window as Window & { SERVICE_CONFIG?: unknown }).SERVICE_CONFIG
    const state = useServiceCategories()
    expect(state.enableAdminSync.value).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Pane: setStore → loadCategories
// ---------------------------------------------------------------------------

describe('useServiceCategories — pane setStore', () => {
  it('loads categories when a store is selected', async () => {
    vi.mocked(client.fetchCategoriesForStore).mockResolvedValue(categories)
    const state = useServiceCategories()
    await flushPromises()

    state.targetPane.setStore(1)
    await flushPromises()

    expect(client.fetchCategoriesForStore).toHaveBeenCalledWith(1)
    expect(state.targetPane.categories.value).toHaveLength(2)
    expect(state.targetPane.statusKind.value).toBe('success')
  })

  it('clears categories and shows idle status when store set to null', async () => {
    const state = useServiceCategories()
    await flushPromises()

    state.targetPane.setStore(null)
    await flushPromises()

    expect(state.targetPane.categories.value).toEqual([])
    expect(state.targetPane.statusKind.value).toBe('info')
  })

  it('sets error status when fetchCategoriesForStore fails', async () => {
    vi.mocked(client.fetchCategoriesForStore).mockRejectedValue(new Error('Network error'))
    const state = useServiceCategories()
    await flushPromises()

    state.targetPane.setStore(1)
    await flushPromises()

    expect(state.targetPane.statusKind.value).toBe('error')
    expect(state.targetPane.categories.value).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// Pane: triggerSync
// ---------------------------------------------------------------------------

describe('useServiceCategories — pane triggerSync', () => {
  it('shows warning when no store selected', async () => {
    const state = useServiceCategories()
    await flushPromises()

    await state.targetPane.triggerSync()

    expect(state.targetPane.statusKind.value).toBe('warning')
    expect(client.syncStoreCategories).not.toHaveBeenCalled()
  })

  it('calls syncStoreCategories and updates categories on success', async () => {
    const state = useServiceCategories()
    await flushPromises()

    state.targetPane.storeId.value = 1
    await state.targetPane.triggerSync()
    await flushPromises()

    expect(client.syncStoreCategories).toHaveBeenCalledWith(1)
    expect(state.targetPane.categories.value).toHaveLength(2)
    expect(state.targetPane.statusKind.value).toBe('success')
  })

  it('reloads scrape status after sync', async () => {
    const state = useServiceCategories()
    await flushPromises()
    vi.clearAllMocks()
    vi.mocked(client.syncStoreCategories).mockResolvedValue(categories)
    vi.mocked(client.fetchScrapeStatus).mockResolvedValue([])

    state.targetPane.storeId.value = 1
    await state.targetPane.triggerSync()
    await flushPromises()

    expect(client.fetchScrapeStatus).toHaveBeenCalled()
  })

  it('sets error status on sync failure', async () => {
    vi.mocked(client.syncStoreCategories).mockRejectedValue(new Error('Server error'))
    const state = useServiceCategories()
    await flushPromises()

    state.targetPane.storeId.value = 1
    await state.targetPane.triggerSync()
    await flushPromises()

    expect(state.targetPane.statusKind.value).toBe('error')
  })
})

// ---------------------------------------------------------------------------
// Pane: triggerProductSync
// ---------------------------------------------------------------------------

describe('useServiceCategories — pane triggerProductSync', () => {
  it('calls syncCategoryProducts and shows summary', async () => {
    const state = useServiceCategories()
    await flushPromises()

    await state.targetPane.triggerProductSync(10)
    await flushPromises()

    expect(client.syncCategoryProducts).toHaveBeenCalledWith(10)
    expect(state.targetPane.statusKind.value).toBe('success')
    expect(state.targetPane.statusText.value).toContain('оброблено 10')
  })

  it('sets error status on product sync failure', async () => {
    vi.mocked(client.syncCategoryProducts).mockRejectedValue(new Error('Timeout'))
    const state = useServiceCategories()
    await flushPromises()

    await state.targetPane.triggerProductSync(10)
    await flushPromises()

    expect(state.targetPane.statusKind.value).toBe('error')
  })
})

// ---------------------------------------------------------------------------
// Admin store sync
// ---------------------------------------------------------------------------

describe('useServiceCategories — triggerStoreSync', () => {
  it('calls syncAdminStores and updates stores list', async () => {
    const newStores = [{ id: 3, name: 'newshop', is_reference: false, base_url: null }]
    vi.mocked(client.syncAdminStores).mockResolvedValue(newStores)
    const state = useServiceCategories()
    await flushPromises()

    state.triggerStoreSync()
    await flushPromises()

    expect(client.syncAdminStores).toHaveBeenCalled()
    expect(state.stores.value).toHaveLength(1)
    expect(state.storeSyncStatus.value?.kind).toBe('success')
  })

  it('sets error status when syncAdminStores fails', async () => {
    vi.mocked(client.syncAdminStores).mockRejectedValue(new Error('Forbidden'))
    const state = useServiceCategories()
    await flushPromises()

    state.triggerStoreSync()
    await flushPromises()

    expect(state.storeSyncStatus.value?.kind).toBe('error')
  })
})

