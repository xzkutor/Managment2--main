import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { flushPromises } from '@vue/test-utils'

// ---------------------------------------------------------------------------
// Mock API modules
// ---------------------------------------------------------------------------

vi.mock('@/api/client', () => ({
  fetchStores: vi.fn(),
  fetchCategoriesForStore: vi.fn(),
}))

vi.mock('@/api/gap', () => ({
  fetchMappedTargetCategories: vi.fn(),
  postGapQuery: vi.fn(),
  postGapStatus: vi.fn(),
}))

import * as clientApi from '@/api/client'
import * as gapApi from '@/api/gap'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const stores = [
  { id: 1, name: 'prohockey', is_reference: true, base_url: null },
  { id: 2, name: 'hockeyworld', is_reference: false, base_url: null },
]

const refCategories = [
  { id: 10, store_id: 1, name: 'Ковзани', normalized_name: null, url: null, external_id: null, updated_at: null },
]

const mappedCats = [
  { target_category_id: 20, target_category_name: 'Skates', target_store_id: 2 },
  { target_category_id: 21, target_category_name: 'Skates Pro', target_store_id: 2 },
]

const gapResult = {
  summary: { total: 2, new: 1, in_progress: 1, done: 0 },
  groups: [
    {
      target_category: { id: 20, name: 'Skates' },
      count: 2,
      items: [
        { status: 'new' as const, target_product: { id: 100, name: 'Bauer X', price: '1500.00', currency: 'UAH', is_available: true, product_url: 'http://a.com/1' } },
        { status: 'in_progress' as const, target_product: { id: 101, name: 'CCM Tacks', price: '2000.00', currency: 'UAH', is_available: false, product_url: null } },
      ],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(clientApi.fetchStores).mockResolvedValue(stores)
  vi.mocked(clientApi.fetchCategoriesForStore).mockResolvedValue(refCategories)
  vi.mocked(gapApi.fetchMappedTargetCategories).mockResolvedValue(mappedCats)
  vi.mocked(gapApi.postGapQuery).mockResolvedValue(gapResult)
  vi.mocked(gapApi.postGapStatus).mockResolvedValue(undefined)
})

// ---------------------------------------------------------------------------
// useGapFilters tests
// ---------------------------------------------------------------------------

import { useGapFilters } from '@/pages/gap/composables/useGapFilters'

describe('useGapFilters — initial state', () => {
  it('is empty before loadStores', () => {
    const f = useGapFilters()
    expect(f.targetStores.value).toHaveLength(0)
    expect(f.referenceStores.value).toHaveLength(0)
  })

  it('loads and splits stores', async () => {
    const f = useGapFilters()
    await f.loadStores()
    await flushPromises()
    expect(f.targetStores.value).toHaveLength(1)
    expect(f.referenceStores.value).toHaveLength(1)
  })

  it('canLoad is false initially', () => {
    const f = useGapFilters()
    expect(f.canLoad.value).toBe(false)
  })
})

describe('useGapFilters — cascade loading', () => {
  it('setTargetStore loads reference categories from first ref store', async () => {
    const f = useGapFilters()
    await f.loadStores()
    await flushPromises()
    await f.setTargetStore(2)
    await flushPromises()
    expect(clientApi.fetchCategoriesForStore).toHaveBeenCalledWith(1) // ref store id
    expect(f.referenceCategories.value).toHaveLength(1)
  })

  it('setTargetStore clears previous ref category selection', async () => {
    const f = useGapFilters()
    await f.loadStores()
    f.selectedRefCategoryId.value = 10
    await f.setTargetStore(2)
    expect(f.selectedRefCategoryId.value).toBeNull()
  })

  it('setRefCategory loads mapped target categories', async () => {
    const f = useGapFilters()
    await f.loadStores()
    await flushPromises()
    f.selectedTargetStoreId.value = 2
    await f.setRefCategory(10)
    await flushPromises()
    expect(gapApi.fetchMappedTargetCategories).toHaveBeenCalledWith(10, 2)
    expect(f.mappedTargetCats.value).toHaveLength(2)
    expect(f.selectedTargetCatIds.value.size).toBe(2) // all checked by default
  })

  it('shows noMappingsWarning when no mapped cats', async () => {
    vi.mocked(gapApi.fetchMappedTargetCategories).mockResolvedValue([])
    const f = useGapFilters()
    f.selectedTargetStoreId.value = 2
    await f.setRefCategory(10)
    await flushPromises()
    expect(f.noMappingsWarning.value).toBe(true)
    expect(f.canLoad.value).toBe(false)
  })

  it('canLoad is true when mapped cats are selected', async () => {
    const f = useGapFilters()
    await f.loadStores()
    await flushPromises()
    f.selectedTargetStoreId.value = 2
    await f.setRefCategory(10)
    await flushPromises()
    expect(f.canLoad.value).toBe(true)
  })

  it('toggleTargetCat removes id from set', async () => {
    const f = useGapFilters()
    f.selectedTargetStoreId.value = 2
    await f.setRefCategory(10)
    await flushPromises()
    f.toggleTargetCat(20, false)
    expect(f.selectedTargetCatIds.value.has(20)).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// useGapData tests
// ---------------------------------------------------------------------------

import { useGapData } from '@/pages/gap/composables/useGapData'

const sampleBody = {
  target_store_id: 2,
  reference_category_id: 10,
  target_category_ids: [20, 21],
  search: null,
  only_available: null,
  statuses: ['new' as const, 'in_progress' as const],
}

describe('useGapData', () => {
  it('loads gap result', async () => {
    const d = useGapData()
    await d.loadGap(sampleBody)
    expect(gapApi.postGapQuery).toHaveBeenCalledWith(sampleBody)
    expect(d.result.value?.summary.total).toBe(2)
    expect(d.hasLoaded.value).toBe(true)
  })

  it('stores lastBody for reload', async () => {
    const d = useGapData()
    await d.loadGap(sampleBody)
    expect(d.lastBody.value).toEqual(sampleBody)
  })

  it('sets error on API failure', async () => {
    vi.mocked(gapApi.postGapQuery).mockRejectedValue(new Error('Network fail'))
    const d = useGapData()
    await d.loadGap(sampleBody)
    expect(d.error.value).toContain('Network fail')
    expect(d.hasLoaded.value).toBe(false)
  })

  it('does NOT clear result during subsequent reload (non-destructive)', async () => {
    const d = useGapData()
    await d.loadGap(sampleBody)
    const firstResult = d.result.value

    // Block second load
    let resolve!: (v: typeof gapResult) => void
    vi.mocked(gapApi.postGapQuery).mockReturnValue(
      new Promise<typeof gapResult>((r) => { resolve = r }),
    )

    const loadPromise = d.loadGap(sampleBody)
    // result still visible while loading
    expect(d.result.value).toBe(firstResult)
    expect(d.hasLoaded.value).toBe(true)

    resolve(gapResult)
    await loadPromise
    expect(d.result.value).not.toBeNull()
  })
})

// ---------------------------------------------------------------------------
// patchGapResult unit tests
// ---------------------------------------------------------------------------

import { patchGapItemStatus } from '@/pages/gap/composables/patchGapResult'

describe('patchGapItemStatus', () => {
  it('updates status of the matching item', () => {
    const patched = patchGapItemStatus(gapResult, 100, 'in_progress')
    const item = patched.groups[0].items.find((i) => i.target_product?.id === 100)
    expect(item?.status).toBe('in_progress')
  })

  it('recalculates summary counters correctly', () => {
    // Original: new=1, in_progress=1
    const patched = patchGapItemStatus(gapResult, 100, 'done')
    // Item 100 was 'new' → now 'done'; item 101 stays 'in_progress'
    expect(patched.summary.new).toBe(0)
    expect(patched.summary.in_progress).toBe(1)
    expect(patched.summary.done).toBe(1)
  })

  it('preserves total in summary', () => {
    const patched = patchGapItemStatus(gapResult, 100, 'done')
    expect(patched.summary.total).toBe(gapResult.summary.total)
  })

  it('returns original result unchanged when targetProductId not found', () => {
    const patched = patchGapItemStatus(gapResult, 9999, 'done')
    expect(patched).toBe(gapResult)
  })

  it('does not mutate the original result', () => {
    const originalStatus = gapResult.groups[0].items[0].status
    patchGapItemStatus(gapResult, 100, 'done')
    expect(gapResult.groups[0].items[0].status).toBe(originalStatus)
  })
})

// ---------------------------------------------------------------------------
// useGapActions tests
// ---------------------------------------------------------------------------

import { useGapActions } from '@/pages/gap/composables/useGapActions'

describe('useGapActions', () => {
  it('calls postGapStatus and returns true on success', async () => {
    const a = useGapActions()
    const ok = await a.setStatus(10, 100, 'in_progress')
    expect(gapApi.postGapStatus).toHaveBeenCalledWith(10, 100, 'in_progress')
    expect(ok).toBe(true)
    expect(a.actionError.value).toBeNull()
  })

  it('returns false and sets error on failure', async () => {
    vi.mocked(gapApi.postGapStatus).mockRejectedValue(new Error('Status error'))
    const a = useGapActions()
    const ok = await a.setStatus(10, 100, 'done')
    expect(ok).toBe(false)
    expect(a.actionError.value).toContain('Status error')
  })

  it('clears actionInProgressId after action', async () => {
    const a = useGapActions()
    await a.setStatus(10, 100, 'in_progress')
    expect(a.actionInProgressId.value).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// GapGroupTable component tests
// ---------------------------------------------------------------------------

import GapGroupTable from '@/pages/gap/components/GapGroupTable.vue'

describe('GapGroupTable', () => {
  const group = gapResult.groups[0]

  it('renders category name and count', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    expect(w.text()).toContain('Skates')
    expect(w.text()).toContain('2 товарів')
  })

  it('renders new item with "Взяти в роботу" button', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    expect(w.text()).toContain('Взяти в роботу')
  })

  it('renders in_progress item with "Позначити опрацьованим" button', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    expect(w.text()).toContain('Позначити опрацьованим')
  })

  it('emits action on "Взяти в роботу" click', async () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    const btn = w.findAll('button').find((b) => b.text().includes('Взяти в роботу'))
    await btn!.trigger('click')
    expect(w.emitted('action')).toBeTruthy()
    expect(w.emitted('action')![0]).toEqual([10, 100, 'in_progress'])
  })

  it('disables button when actionInProgressId matches', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: 100 },
    })
    const btn = w.findAll('button')[0]
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('renders price with currency', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    expect(w.text()).toContain('1500.00 UAH')
  })
})

// ---------------------------------------------------------------------------
// GapSummary component tests (Commit 4 — KPI strip + context header)
// ---------------------------------------------------------------------------

import GapSummary from '@/pages/gap/components/GapSummary.vue'

describe('GapSummary', () => {
  it('renders all four KPI counters', () => {
    const w = mount(GapSummary, {
      props: { summary: { total: 10, new: 4, in_progress: 3, done: 3 } },
    })
    expect(w.text()).toContain('10')
    expect(w.text()).toContain('4')
    expect(w.text()).toContain('3')
    expect(w.text()).toContain('Усього')
    expect(w.text()).toContain('Нові')
    expect(w.text()).toContain('В роботі')
    expect(w.text()).toContain('Опрацьовано')
  })

  it('renders context strip when targetStoreName is provided', () => {
    const w = mount(GapSummary, {
      props: {
        summary: { total: 5, new: 2, in_progress: 2, done: 1 },
        targetStoreName: 'hockeyworld',
        refCategoryName: 'Ковзани',
        targetCatCount: 3,
      },
    })
    expect(w.text()).toContain('hockeyworld')
    expect(w.text()).toContain('Ковзани')
    expect(w.text()).toContain('3')
  })

  it('does not render context strip when no store/category provided', () => {
    const w = mount(GapSummary, {
      props: { summary: { total: 5, new: 2, in_progress: 2, done: 1 } },
    })
    expect(w.find('.gap-kpi-context').exists()).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// GapPreRunPlaceholder tests (Commit 3)
// ---------------------------------------------------------------------------

import GapPreRunPlaceholder from '@/pages/gap/components/GapPreRunPlaceholder.vue'

describe('GapPreRunPlaceholder', () => {
  it('renders workflow steps', () => {
    const w = mount(GapPreRunPlaceholder, { props: { canLoad: false } })
    expect(w.text()).toContain('цільовий магазин')
    expect(w.text()).toContain('референсну категорію')
    expect(w.text()).toContain('Показати розрив')
  })

  it('shows ready hint when canLoad is true', () => {
    const w = mount(GapPreRunPlaceholder, { props: { canLoad: true } })
    expect(w.text()).toContain('Усе готово')
  })

  it('does not show ready hint when canLoad is false', () => {
    const w = mount(GapPreRunPlaceholder, { props: { canLoad: false } })
    expect(w.text()).not.toContain('Усе готово')
  })
})

// ---------------------------------------------------------------------------
// GapStatusBanner tests (Commit 5 — in-surface states + refreshing)
// ---------------------------------------------------------------------------

import GapStatusBanner from '@/pages/gap/components/GapStatusBanner.vue'

describe('GapStatusBanner', () => {
  it('shows initial loading block when loading and not yet loaded', () => {
    const w = mount(GapStatusBanner, {
      props: { loading: true, error: null, isEmpty: false, hasLoaded: false, storesError: null },
    })
    expect(w.text()).toContain('Завантаження')
    expect(w.find('.gap-surface-refreshing').exists()).toBe(false)
  })

  it('shows refreshing bar when loading and already loaded (non-destructive reload)', () => {
    const w = mount(GapStatusBanner, {
      props: { loading: true, error: null, isEmpty: false, hasLoaded: true, storesError: null },
    })
    expect(w.find('.gap-surface-refreshing').exists()).toBe(true)
    expect(w.text()).toContain('Оновлення')
  })

  it('shows error message', () => {
    const w = mount(GapStatusBanner, {
      props: { loading: false, error: 'Test error', isEmpty: false, hasLoaded: true, storesError: null },
    })
    expect(w.text()).toContain('Test error')
    expect(w.find('.error').exists()).toBe(true)
  })

  it('shows stores error message', () => {
    const w = mount(GapStatusBanner, {
      props: { loading: false, error: null, isEmpty: false, hasLoaded: false, storesError: 'Store fail' },
    })
    expect(w.text()).toContain('Store fail')
  })

  it('shows empty state when loaded and empty', () => {
    const w = mount(GapStatusBanner, {
      props: { loading: false, error: null, isEmpty: true, hasLoaded: true, storesError: null },
    })
    expect(w.find('.empty-state').exists()).toBe(true)
    expect(w.text()).toContain('Розрив відсутній')
  })

  it('shows nothing when loaded with results', () => {
    const w = mount(GapStatusBanner, {
      props: { loading: false, error: null, isEmpty: false, hasLoaded: true, storesError: null },
    })
    expect(w.html().trim()).toBe('<!--v-if-->')
  })
})

// ---------------------------------------------------------------------------
// useGapData workspace state helpers (Commit 1)
// ---------------------------------------------------------------------------

describe('useGapData — workspace state helpers', () => {
  it('hasNeverLoaded is true before any load', () => {
    const d = useGapData()
    expect(d.hasNeverLoaded.value).toBe(true)
    expect(d.hasResults.value).toBe(false)
    expect(d.isEmptyAfterLoad.value).toBe(false)
    expect(d.hasBlockingError.value).toBe(false)
  })

  it('hasResults is true after loading a non-empty result', async () => {
    const d = useGapData()
    await d.loadGap(sampleBody)
    expect(d.hasResults.value).toBe(true)
    expect(d.isEmptyAfterLoad.value).toBe(false)
    expect(d.hasNeverLoaded.value).toBe(false)
  })

  it('isEmptyAfterLoad is true when result has no groups', async () => {
    vi.mocked(gapApi.postGapQuery).mockResolvedValue({ summary: { total: 0, new: 0, in_progress: 0, done: 0 }, groups: [] })
    const d = useGapData()
    await d.loadGap(sampleBody)
    expect(d.isEmptyAfterLoad.value).toBe(true)
    expect(d.hasResults.value).toBe(false)
  })

  it('hasBlockingError is true after API failure', async () => {
    vi.mocked(gapApi.postGapQuery).mockRejectedValue(new Error('fail'))
    const d = useGapData()
    await d.loadGap(sampleBody)
    expect(d.hasBlockingError.value).toBe(true)
    expect(d.hasNeverLoaded.value).toBe(false)
  })

  it('hasNeverLoaded is false while loading', async () => {
    let resolve!: (v: typeof gapResult) => void
    vi.mocked(gapApi.postGapQuery).mockReturnValue(new Promise<typeof gapResult>((r) => { resolve = r }))
    const d = useGapData()
    const loadPromise = d.loadGap(sampleBody)
    // During loading: hasNeverLoaded should be false (loading=true)
    expect(d.hasNeverLoaded.value).toBe(false)
    resolve(gapResult)
    await loadPromise
  })
})

// ---------------------------------------------------------------------------
// GapGroupTable workspace panel tests (Commits 6, 8)
// ---------------------------------------------------------------------------

describe('GapGroupTable — workspace panel', () => {
  const group = gapResult.groups[0]

  it('renders panel with category heading', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    expect(w.find('.gap-group-panel').exists()).toBe(true)
    expect(w.find('.gap-group-title').text()).toContain('Skates')
  })

  it('renders compact row for each item', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    expect(w.findAll('.gap-row')).toHaveLength(2)
  })

  it('shows spinner for in-progress row action', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: 100 },
    })
    expect(w.find('.gap-row-action-pending').exists()).toBe(true)
    expect(w.find('.spinner').exists()).toBe(true)
  })

  it('availability badge shows yes for available item', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    expect(w.find('.gap-avail--yes').exists()).toBe(true)
  })

  it('availability badge shows no for unavailable item', () => {
    const w = mount(GapGroupTable, {
      props: { group, refCategoryId: 10, actionInProgressId: null },
    })
    expect(w.find('.gap-avail--no').exists()).toBe(true)
  })
})

