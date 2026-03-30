/**
 * ServiceCategoriesTab.test.ts — Commit 09 assertions for the redesigned
 * Categories section.
 *
 * Key assertions:
 *  1. Only ONE store selector is visible (no dual-pane reference selector).
 *  2. Reference stores are NOT rendered as options.
 *  3. Target (non-reference) stores ARE rendered as options.
 *  4. Selecting a store updates both the pane and the shared service context.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { computed, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ServiceCategoriesTab from '@/pages/service/categories/ServiceCategoriesTab.vue'

// ---------------------------------------------------------------------------
// Stub heavy child components — layout/structural test only
// ---------------------------------------------------------------------------
vi.mock('@/pages/service/categories/components/ScrapeStatusList.vue', () => ({
  default: { template: '<div data-testid="scrape-status-list"></div>' },
}))
vi.mock('@/pages/service/categories/components/CategoryTable.vue', () => ({
  default: { template: '<div data-testid="category-table"></div>' },
}))

// ---------------------------------------------------------------------------
// Mock composables
// ---------------------------------------------------------------------------
vi.mock('@/pages/service/categories/composables/useServiceCategories')
vi.mock('@/pages/service/composables/useServiceContext')

import { useServiceCategories } from '@/pages/service/categories/composables/useServiceCategories'
import { useServiceContext } from '@/pages/service/composables/useServiceContext'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const refStore   = { id: 1, name: 'prohockey',   is_reference: true,  base_url: null }
const targetStore = { id: 2, name: 'hockeyworld', is_reference: false, base_url: null }

function makePaneMock() {
  return {
    storeId:               ref<number | null>(null),
    categories:            ref([]),
    loading:               ref(false),
    statusText:            ref('Очікування'),
    statusKind:            ref('info'),
    syncLoading:           ref(false),
    syncProductsLoadingId: ref<number | null>(null),
    setStore:              vi.fn(),
    loadCategories:        vi.fn(),
    triggerSync:           vi.fn(),
    triggerProductSync:    vi.fn(),
  }
}

function makeStateMock(stores = [refStore, targetStore]) {
  return {
    enableAdminSync:    computed(() => false),
    stores:             ref(stores),
    storesLoading:      ref(false),
    storeSyncLoading:   ref(false),
    storeSyncStatus:    ref(null),
    triggerStoreSync:   vi.fn(),
    refPane:            makePaneMock(),
    targetPane:         makePaneMock(),
    scrapeRuns:         ref([]),
    scrapeRunsLoading:  ref(false),
    reloadScrapeStatus: vi.fn(),
  }
}

const mockSetTargetStore = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useServiceCategories).mockReturnValue(makeStateMock() as never)
  vi.mocked(useServiceContext).mockReturnValue({
    currentTargetStoreId: ref(null),
    setTargetStore: mockSetTargetStore,
  })
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ServiceCategoriesTab — no reference store selector', () => {
  it('renders exactly one <select> element (target-store only; no dual-pane)', () => {
    const w = mount(ServiceCategoriesTab)
    expect(w.findAll('select')).toHaveLength(1)
  })

  it('does NOT include reference stores in the selector', () => {
    const w = mount(ServiceCategoriesTab)
    const optionTexts = w.find('select').findAll('option').map((o) => o.text())
    expect(optionTexts.some((t) => t.includes('prohockey'))).toBe(false)
  })

  it('includes non-reference (target) stores in the selector', () => {
    const w = mount(ServiceCategoriesTab)
    const optionTexts = w.find('select').findAll('option').map((o) => o.text())
    expect(optionTexts.some((t) => t.includes('hockeyworld'))).toBe(true)
  })

  it('calls targetPane.setStore when a store is selected', async () => {
    const state = makeStateMock()
    vi.mocked(useServiceCategories).mockReturnValue(state as never)
    const w = mount(ServiceCategoriesTab)

    await w.find('select').setValue('2')

    expect(state.targetPane.setStore).toHaveBeenCalledWith(2)
  })

  it('updates the shared service context when a store is selected', async () => {
    const w = mount(ServiceCategoriesTab)
    await w.find('select').setValue('2')
    expect(mockSetTargetStore).toHaveBeenCalledWith(2)
  })

  it('sets service context to null when blank option is selected', async () => {
    const w = mount(ServiceCategoriesTab)
    await w.find('select').setValue('')
    expect(mockSetTargetStore).toHaveBeenCalledWith(null)
  })

  it('renders the category table surface', () => {
    const w = mount(ServiceCategoriesTab)
    expect(w.find('[data-testid="category-table"]').exists()).toBe(true)
  })
})

describe('ServiceCategoriesTab — with only target stores available', () => {
  it('shows a store option when only target stores exist', () => {
    vi.mocked(useServiceCategories).mockReturnValue(
      makeStateMock([targetStore]) as never,
    )
    const w = mount(ServiceCategoriesTab)
    const opts = w.find('select').findAll('option')
    // placeholder + 1 target store
    expect(opts.length).toBeGreaterThanOrEqual(2)
    expect(opts.some((o) => o.text().includes('hockeyworld'))).toBe(true)
  })

  it('shows no store options (only placeholder) when no target stores exist', () => {
    vi.mocked(useServiceCategories).mockReturnValue(
      makeStateMock([refStore]) as never, // only ref store — filtered out
    )
    const w = mount(ServiceCategoriesTab)
    const opts = w.find('select').findAll('option')
    // only the placeholder option
    expect(opts).toHaveLength(1)
  })
})

