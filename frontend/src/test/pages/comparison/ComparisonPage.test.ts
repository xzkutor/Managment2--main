import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// ---------------------------------------------------------------------------
// Mock API modules
// ---------------------------------------------------------------------------

vi.mock('@/api/client', () => ({
  fetchStores: vi.fn(),
  fetchCategoriesForStore: vi.fn(),
}))

vi.mock('@/pages/comparison/api', () => ({
  fetchStores: vi.fn(),
  fetchCategoriesForStore: vi.fn(),
  fetchMappedTargets: vi.fn(),
  runComparison: vi.fn(),
  saveMatchDecision: vi.fn(),
  searchEligibleTargetProducts: vi.fn(),
}))

import * as compApi from '@/pages/comparison/api'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const refStore  = { id: 1, name: 'prohockey', is_reference: true,  base_url: null }
const tgtStore  = { id: 2, name: 'hockeyworld', is_reference: false, base_url: null }
const stores    = [refStore, tgtStore]

const refCats = [
  { id: 10, store_id: 1, name: 'Ковзани', normalized_name: null, url: 'https://a.com', external_id: null, updated_at: null },
  { id: 11, store_id: 1, name: 'Шлеми',  normalized_name: null, url: null,            external_id: null, updated_at: null },
]

const mappedTargets = [
  { target_category_id: 20, target_category_name: 'Skates', target_store_id: 2, target_store_name: 'hockeyworld', match_type: 'exact' },
  { target_category_id: 21, target_category_name: 'Skates Pro', target_store_id: 2, target_store_name: 'hockeyworld', match_type: null },
]

const comparisonResult = {
  confirmed_matches: [
    {
      is_confirmed: false,
      reference_product: { id: 100, name: 'Bauer X', price: '1500.00', currency: 'UAH', product_url: 'http://a.com/1' },
      target_product:    { id: 200, name: 'Bauer X copy', price: '1480.00', currency: 'UAH', product_url: null },
      target_category:   { name: 'Skates', store_name: 'hockeyworld' },
      score_percent:     90,
      score_details:     null,
    },
  ],
  candidate_groups: [
    {
      reference_product: { id: 101, name: 'CCM Ref', price: '2000.00', currency: 'UAH', product_url: null },
      candidates: [
        {
          target_product: { id: 201, name: 'CCM Copy', price: '1900.00', currency: 'UAH', product_url: null },
          target_category: { name: 'Skates', store_name: 'hockeyworld' },
          score_percent: 70, score_details: null, can_accept: true, disabled_reason: null,
        },
      ],
    },
  ],
  reference_only: [
    { reference_product: { id: 102, name: 'Ref Only Item', price: '500.00', currency: 'UAH', product_url: null } },
  ],
  target_only: [
    {
      target_product:  { id: 202, name: 'Tgt Only Item', price: '400.00', currency: 'UAH', product_url: null },
      target_category: { name: 'Skates Pro', store_name: 'hockeyworld' },
    },
  ],
  summary: { candidate_groups: 1, reference_only: 1, target_only: 1 },
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(compApi.fetchStores).mockResolvedValue(stores)
  vi.mocked(compApi.fetchCategoriesForStore).mockResolvedValue(refCats)
  vi.mocked(compApi.fetchMappedTargets).mockResolvedValue(mappedTargets)
  vi.mocked(compApi.runComparison).mockResolvedValue(comparisonResult)
  vi.mocked(compApi.saveMatchDecision).mockResolvedValue(undefined)
  vi.mocked(compApi.searchEligibleTargetProducts).mockResolvedValue([])
})

// ---------------------------------------------------------------------------
// useComparisonPage unit tests
// ---------------------------------------------------------------------------

import { useComparisonPage } from '@/pages/comparison/composables/useComparisonPage'

describe('useComparisonPage — initial state', () => {
  it('starts with empty stores and no selections', () => {
    const p = useComparisonPage()
    expect(p.referenceStores.value).toHaveLength(0)
    expect(p.targetStores.value).toHaveLength(0)
    expect(p.referenceCategoryId.value).toBeNull()
    expect(p.canCompare.value).toBe(false)
  })

  it('canCompare is false before any selection', () => {
    const p = useComparisonPage()
    expect(p.canCompare.value).toBe(false)
  })
})

describe('useComparisonPage — auto-select single reference store', () => {
  it('auto-selects a single reference store and loads its categories', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()

    expect(p.referenceStoreId.value).toBe(1)
    expect(compApi.fetchCategoriesForStore).toHaveBeenCalledWith(1)
    expect(p.referenceCategories.value).toHaveLength(2)
  })

  it('does NOT auto-select when there are multiple reference stores', async () => {
    vi.mocked(compApi.fetchStores).mockResolvedValue([
      { id: 1, name: 'ref1', is_reference: true, base_url: null },
      { id: 3, name: 'ref2', is_reference: true, base_url: null },
      tgtStore,
    ])
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()

    expect(p.referenceStoreId.value).toBeNull()
    expect(compApi.fetchCategoriesForStore).not.toHaveBeenCalled()
  })
})

describe('useComparisonPage — cascade loading', () => {
  it('selectRefCategory loads mapped targets', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()

    expect(compApi.fetchMappedTargets).toHaveBeenCalledWith(10, null)
    expect(p.mappedTargets.value).toHaveLength(2)
    expect(p.selectedTargetCategoryIds.value.size).toBe(2)
  })

  it('selectRefCategory shows noMappingsWarning when no mapped cats', async () => {
    vi.mocked(compApi.fetchMappedTargets).mockResolvedValue([])
    const p = useComparisonPage()
    p.referenceStoreId.value = 1
    await p.selectRefCategory(10)
    await flushPromises()

    expect(p.noMappingsWarning.value).toBe(true)
    expect(p.canCompare.value).toBe(false)
  })

  it('canCompare becomes true after mapped targets are selected', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()

    expect(p.canCompare.value).toBe(true)
  })

  it('setTargetStore reloads mapped targets if ref category already selected', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()

    vi.mocked(compApi.fetchMappedTargets).mockClear()
    await p.setTargetStore(2)
    await flushPromises()

    expect(compApi.fetchMappedTargets).toHaveBeenCalledWith(10, 2)
  })

  it('toggleTargetCategory removes id from set', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()

    p.toggleTargetCategory(20, false)
    expect(p.selectedTargetCategoryIds.value.has(20)).toBe(false)
  })
})

describe('useComparisonPage — compare button enablement', () => {
  it('compare button is disabled when no ref category selected', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    expect(p.canCompare.value).toBe(false)
  })

  it('compare button is disabled when no target categories checked', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()

    // Uncheck all
    p.toggleTargetCategory(20, false)
    p.toggleTargetCategory(21, false)
    expect(p.canCompare.value).toBe(false)
  })

  it('compare button enabled when ref category + at least one target selected', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    expect(p.canCompare.value).toBe(true)
  })
})

describe('useComparisonPage — comparison execution', () => {
  it('calls runComparison with correct body', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    expect(compApi.runComparison).toHaveBeenCalledWith(
      expect.objectContaining({
        reference_category_id: 10,
        target_category_ids: expect.arrayContaining([20, 21]),
      }),
    )
    expect(p.hasCompared.value).toBe(true)
    expect(p.comparisonResult.value).not.toBeNull()
  })

  it('sets comparisonError on API failure', async () => {
    vi.mocked(compApi.runComparison).mockRejectedValue(new Error('server error'))
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    expect(p.comparisonError.value).toContain('server error')
    expect(p.hasCompared.value).toBe(false)
  })

  it('autoSuggestions filters is_confirmed===false only', async () => {
    vi.mocked(compApi.runComparison).mockResolvedValue({
      ...comparisonResult,
      confirmed_matches: [
        { ...comparisonResult.confirmed_matches[0], is_confirmed: false },
        { ...comparisonResult.confirmed_matches[0], is_confirmed: true,
          reference_product: { id: 999, name: 'Confirmed', price: null, currency: null, product_url: null },
          target_product:    { id: 998, name: 'Persisted', price: null, currency: null, product_url: null },
        },
      ],
    })
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    expect(p.autoSuggestions.value).toHaveLength(1)
    expect(p.autoSuggestions.value[0].is_confirmed).toBe(false)
  })
})

describe('useComparisonPage — makeDecision', () => {
  it('calls saveMatchDecision and does NOT rerun full comparison', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    vi.mocked(compApi.runComparison).mockClear()
    await p.makeDecision(100, 200, 'confirmed')

    expect(compApi.saveMatchDecision).toHaveBeenCalledWith(
      expect.objectContaining({
        reference_product_id: 100,
        target_product_id:    200,
        match_status:         'confirmed',
      }),
    )
    // Local patch — full comparison rerun must NOT happen
    expect(compApi.runComparison).not.toHaveBeenCalled()
  })

  it('removes the acted-on pair from confirmed_matches after decision', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    // confirmed_matches has 1 entry with refId=100, tgtId=200
    expect(p.comparisonResult.value!.confirmed_matches).toHaveLength(1)

    await p.makeDecision(100, 200, 'confirmed')

    expect(p.comparisonResult.value!.confirmed_matches).toHaveLength(0)
  })

  it('removes the matching candidate from candidate_groups after decision', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    // candidate_groups has 1 group (refId=101) with 1 candidate (tgtId=201)
    expect(p.comparisonResult.value!.candidate_groups).toHaveLength(1)

    await p.makeDecision(101, 201, 'rejected')

    // Group becomes empty → removed entirely
    expect(p.comparisonResult.value!.candidate_groups).toHaveLength(0)
    expect(p.comparisonResult.value!.summary.candidate_groups).toBe(0)
  })

  it('keeps comparisonResult non-null and other sections intact after decision', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    const refOnlyBefore = p.comparisonResult.value!.reference_only.length
    const tgtOnlyBefore = p.comparisonResult.value!.target_only.length

    await p.makeDecision(100, 200, 'confirmed')

    expect(p.comparisonResult.value).not.toBeNull()
    expect(p.comparisonResult.value!.reference_only).toHaveLength(refOnlyBefore)
    expect(p.comparisonResult.value!.target_only).toHaveLength(tgtOnlyBefore)
  })

  it('sets decisionError on failure without crashing', async () => {
    vi.mocked(compApi.saveMatchDecision).mockRejectedValue(new Error('conflict'))
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()
    await p.makeDecision(100, 200, 'confirmed')

    expect(p.decisionError.value).toContain('conflict')
    expect(p.decisionInProgressKey.value).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// useManualPicker unit tests
// ---------------------------------------------------------------------------

import { useManualPicker } from '@/pages/comparison/composables/useManualPicker'

describe('useManualPicker', () => {
  it('starts with empty state', () => {
    const picker = useManualPicker(() => 100, () => [20, 21])
    expect(picker.products.value).toHaveLength(0)
    expect(picker.isSearching.value).toBe(false)
    expect(picker.includeRejected.value).toBe(false)
  })

  it('does not search when query is less than 2 chars', async () => {
    const picker = useManualPicker(() => 100, () => [20])
    picker.onSearchInput('a')
    await flushPromises()
    expect(compApi.searchEligibleTargetProducts).not.toHaveBeenCalled()
    expect(picker.products.value).toHaveLength(0)
  })

  it('calls searchEligibleTargetProducts after debounce', async () => {
    vi.useFakeTimers()
    vi.mocked(compApi.searchEligibleTargetProducts).mockResolvedValue([
      { id: 300, name: 'Found product', price: '100', currency: 'UAH', category: null },
    ])
    const picker = useManualPicker(() => 100, () => [20, 21])
    picker.onSearchInput('Bauer')
    vi.runAllTimers()
    await flushPromises()

    expect(compApi.searchEligibleTargetProducts).toHaveBeenCalledWith(
      expect.objectContaining({ referenceProductId: 100, search: 'Bauer', includeRejected: false }),
    )
    expect(picker.products.value).toHaveLength(1)
    vi.useRealTimers()
  })

  it('retriggers search when includeRejected toggles with active query', async () => {
    vi.useFakeTimers()
    const picker = useManualPicker(() => 100, () => [20])
    picker.onSearchInput('Vapor')
    vi.runAllTimers()
    await flushPromises()
    vi.mocked(compApi.searchEligibleTargetProducts).mockClear()

    picker.setIncludeRejected(true)
    vi.runAllTimers()
    await flushPromises()

    expect(compApi.searchEligibleTargetProducts).toHaveBeenCalledWith(
      expect.objectContaining({ includeRejected: true }),
    )
    vi.useRealTimers()
  })
})

// ---------------------------------------------------------------------------
// ComparisonSummaryBar component tests
// ---------------------------------------------------------------------------

import ComparisonSummaryBar from '@/pages/comparison/components/ComparisonSummaryBar.vue'

describe('ComparisonSummaryBar', () => {
  it('shows comparing text when comparing=true', () => {
    const w = mount(ComparisonSummaryBar, {
      props: { result: null, comparing: true, errorText: null, referenceCategory: null, targetStore: null },
    })
    expect(w.text()).toContain('Виконується порівняння')
  })

  it('shows error when errorText is set', () => {
    const w = mount(ComparisonSummaryBar, {
      props: { result: null, comparing: false, errorText: 'Помилка: щось пішло не так', referenceCategory: null, targetStore: null },
    })
    expect(w.text()).toContain('Помилка')
  })

  it('renders KPI cards with correct counts after successful comparison', () => {
    const w = mount(ComparisonSummaryBar, {
      props: { result: comparisonResult, comparing: false, errorText: null, referenceCategory: null, targetStore: null },
    })
    // KPI labels
    expect(w.text()).toContain('Авто-пропозиції')
    expect(w.text()).toContain('Кандидати')
    expect(w.text()).toContain('Тільки в референсі')
    expect(w.text()).toContain('Тільки в цільовому')
    // KPI numbers: all sections have 1 item in the fixture
    const kpiNums = w.findAll('.kpi-num').map(n => n.text())
    expect(kpiNums).toContain('1')
  })

  it('shows nothing when result is null and not comparing', () => {
    const w = mount(ComparisonSummaryBar, {
      props: { result: null, comparing: false, errorText: null, referenceCategory: null, targetStore: null },
    })
    expect(w.text().trim()).toBe('')
  })

  it('renders context strip when referenceCategory is provided', () => {
    const refCat = refCats[0]
    const w = mount(ComparisonSummaryBar, {
      props: { result: comparisonResult, comparing: false, errorText: null, referenceCategory: refCat, targetStore: null },
    })
    expect(w.text()).toContain('Ковзани')
  })
})

// ---------------------------------------------------------------------------
// ReferenceCategoryList component tests
// ---------------------------------------------------------------------------

import ReferenceCategoryList from '@/pages/comparison/components/ReferenceCategoryList.vue'

describe('ReferenceCategoryList', () => {
  it('renders category names', () => {
    const w = mount(ReferenceCategoryList, {
      props: { categories: refCats, activeCategoryId: null, loading: false },
    })
    expect(w.text()).toContain('Ковзани')
    expect(w.text()).toContain('Шлеми')
  })

  it('emits select on click', async () => {
    const w = mount(ReferenceCategoryList, {
      props: { categories: refCats, activeCategoryId: null, loading: false },
    })
    await w.findAll('[role="button"]')[0].trigger('click')
    expect(w.emitted('select')).toBeTruthy()
    expect(w.emitted('select')![0]).toEqual([10])
  })

  it('marks active category', () => {
    const w = mount(ReferenceCategoryList, {
      props: { categories: refCats, activeCategoryId: 10, loading: false },
    })
    const items = w.findAll('.category-item')
    expect(items[0].classes()).toContain('active')
    expect(items[1].classes()).not.toContain('active')
  })

  it('shows loading message when loading=true', () => {
    const w = mount(ReferenceCategoryList, {
      props: { categories: [], activeCategoryId: null, loading: true },
    })
    expect(w.text()).toContain('Завантаження')
  })
})

// ---------------------------------------------------------------------------
// MappedTargetCategoryList component tests
// ---------------------------------------------------------------------------

import MappedTargetCategoryList from '@/pages/comparison/components/MappedTargetCategoryList.vue'

describe('MappedTargetCategoryList', () => {
  it('renders checkboxes for each mapped target', () => {
    const w = mount(MappedTargetCategoryList, {
      props: {
        mappedTargets,
        selectedIds:        new Set([20, 21]),
        selectedCategoryId: 10,
        loading:            false,
        noMappingsWarning:  false,
      },
    })
    expect(w.findAll('input[type="checkbox"]')).toHaveLength(2)
  })

  it('shows warning when noMappingsWarning=true', () => {
    const w = mount(MappedTargetCategoryList, {
      props: {
        mappedTargets:      [],
        selectedIds:        new Set<number>(),
        selectedCategoryId: 10,
        loading:            false,
        noMappingsWarning:  true,
      },
    })
    expect(w.text()).toContain('ще не створено меппінг')
    expect(w.html()).toContain('/service')
  })

  it('emits toggle with correct args on checkbox change', async () => {
    const w = mount(MappedTargetCategoryList, {
      props: {
        mappedTargets,
        selectedIds:        new Set([20, 21]),
        selectedCategoryId: 10,
        loading:            false,
        noMappingsWarning:  false,
      },
    })
    const cb = w.findAll('input[type="checkbox"]')[0]
    await cb.setValue(false)
    expect(w.emitted('toggle')).toBeTruthy()
    expect(w.emitted('toggle')![0][0]).toBe(20)
    expect(w.emitted('toggle')![0][1]).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// RFC-016 view-model — reviewCounts / hasReviewContent / comparisonWorkspaceState
// ---------------------------------------------------------------------------

describe('useComparisonPage — workspace view-model (RFC-016)', () => {
  it('hasReviewContent is false before comparison', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    expect(p.hasReviewContent.value).toBe(false)
  })

  it('hasReviewContent is true after comparison with results', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    expect(p.hasReviewContent.value).toBe(true)
  })

  it('comparisonWorkspaceState is idle initially', () => {
    const p = useComparisonPage()
    expect(p.comparisonWorkspaceState.value).toBe('idle')
  })

  it('comparisonWorkspaceState is review when results available', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    expect(p.comparisonWorkspaceState.value).toBe('review')
  })

  it('reviewCounts.autoSuggestions reflects auto-suggestion count', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    // fixture has 1 confirmed_match with is_confirmed=false
    expect(p.reviewCounts.value.autoSuggestions).toBe(1)
    expect(p.reviewCounts.value.candidateGroups).toBe(1)
    expect(p.reviewCounts.value.referenceOnly).toBe(1)
    expect(p.reviewCounts.value.targetOnly).toBe(1)
  })

  it('currentReferenceCategory matches selected category', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()

    expect(p.currentReferenceCategory.value?.id).toBe(10)
    expect(p.currentReferenceCategory.value?.name).toBe('Ковзани')
  })

  it('selectedTargetStore is null when no target store selected', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()

    expect(p.selectedTargetStore.value).toBeNull()
  })

  it('selectedTargetStore reflects selected store after setTargetStore', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.setTargetStore(2)
    await flushPromises()

    expect(p.selectedTargetStore.value?.id).toBe(2)
    expect(p.selectedTargetStore.value?.name).toBe('hockeyworld')
  })
})

// ---------------------------------------------------------------------------
// RFC-016 — reference_only removal after manual match decision
// ---------------------------------------------------------------------------

describe('useComparisonPage — reference_only removal after drawer pick', () => {
  it('removes the reference_only item after makeDecision for that refProductId', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    // fixture has 1 reference_only item (refId=102)
    expect(p.comparisonResult.value!.reference_only).toHaveLength(1)

    await p.makeDecision(102, 999, 'confirmed')

    expect(p.comparisonResult.value!.reference_only).toHaveLength(0)
    expect(p.comparisonResult.value!.summary.reference_only).toBe(0)
  })

  it('reviewCounts.referenceOnly decrements after drawer pick', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    expect(p.reviewCounts.value.referenceOnly).toBe(1)
    await p.makeDecision(102, 999, 'confirmed')
    expect(p.reviewCounts.value.referenceOnly).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// RFC-016 — ComparisonControlRail component (no reference selector visible)
// ---------------------------------------------------------------------------

import ComparisonControlRail from '@/pages/comparison/components/ComparisonControlRail.vue'

describe('ComparisonControlRail', () => {
  it('renders a target store selector', () => {
    const w = mount(ComparisonControlRail, {
      props: {
        targetStores:      [tgtStore],
        targetStoreId:     null,
        categories:        refCats,
        loadingCategories: false,
        activeCategoryId:  null,
        canCompare:        false,
        comparing:         false,
        statusText:        '',
      },
    })
    // Must have a select with target store options
    expect(w.find('select').exists()).toBe(true)
    expect(w.text()).toContain('hockeyworld')
  })

  it('does NOT render a reference store selector', () => {
    const w = mount(ComparisonControlRail, {
      props: {
        targetStores:      [tgtStore],
        targetStoreId:     null,
        categories:        refCats,
        loadingCategories: false,
        activeCategoryId:  null,
        canCompare:        false,
        comparing:         false,
        statusText:        '',
      },
    })
    // Only one select (target store); no reference store select
    expect(w.findAll('select')).toHaveLength(1)
    // Reference stores are not passed as a prop at all
    expect(w.text()).not.toContain('Референсний магазин')
  })

  it('renders reference category list', () => {
    const w = mount(ComparisonControlRail, {
      props: {
        targetStores:      [],
        targetStoreId:     null,
        categories:        refCats,
        loadingCategories: false,
        activeCategoryId:  null,
        canCompare:        false,
        comparing:         false,
        statusText:        '',
      },
    })
    expect(w.text()).toContain('Ковзани')
    expect(w.text()).toContain('Шлеми')
  })

  it('emits select-category on category click', async () => {
    const w = mount(ComparisonControlRail, {
      props: {
        targetStores:      [],
        targetStoreId:     null,
        categories:        refCats,
        loadingCategories: false,
        activeCategoryId:  null,
        canCompare:        false,
        comparing:         false,
        statusText:        '',
      },
    })
    await w.findAll('[role="button"]')[0].trigger('click')
    expect(w.emitted('select-category')).toBeTruthy()
    expect(w.emitted('select-category')![0]).toEqual([10])
  })

  it('renders compare button disabled when canCompare=false', () => {
    const w = mount(ComparisonControlRail, {
      props: {
        targetStores:      [],
        targetStoreId:     null,
        categories:        refCats,
        loadingCategories: false,
        activeCategoryId:  null,
        canCompare:        false,
        comparing:         false,
        statusText:        '',
      },
    })
    const btn = w.find('button')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('emits compare when compare button clicked and canCompare=true', async () => {
    const w = mount(ComparisonControlRail, {
      props: {
        targetStores:      [],
        targetStoreId:     null,
        categories:        refCats,
        loadingCategories: false,
        activeCategoryId:  null,
        canCompare:        true,
        comparing:         false,
        statusText:        '',
      },
    })
    await w.find('button').trigger('click')
    expect(w.emitted('compare')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// RFC-016 — ManualPickerDrawer component
// ---------------------------------------------------------------------------

import ManualPickerDrawer from '@/pages/comparison/components/ManualPickerDrawer.vue'

describe('ManualPickerDrawer', () => {
  it('renders nothing when open=false', () => {
    const w = mount(ManualPickerDrawer, {
      props: { open: false, refProduct: null, targetCategoryIds: [] },
      global: { stubs: { Teleport: true } },
    })
    expect(w.find('.cw-drawer-panel').exists()).toBe(false)
  })

  it('renders panel and ref product name when open=true', () => {
    const refProduct = { id: 100, name: 'Bauer X', price: null, currency: null, product_url: null }
    const w = mount(ManualPickerDrawer, {
      props: { open: true, refProduct, targetCategoryIds: [20] },
      global: { stubs: { Teleport: true } },
    })
    expect(w.find('.cw-drawer-panel').exists()).toBe(true)
    expect(w.text()).toContain('Bauer X')
  })

  it('emits close when close button is clicked', async () => {
    const refProduct = { id: 100, name: 'Bauer X', price: null, currency: null, product_url: null }
    const w = mount(ManualPickerDrawer, {
      props: { open: true, refProduct, targetCategoryIds: [] },
      global: { stubs: { Teleport: true } },
    })
    await w.find('.cw-drawer-close').trigger('click')
    expect(w.emitted('close')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// RFC-016 — TargetOnlySection as secondary section
// ---------------------------------------------------------------------------

import TargetOnlySection from '@/pages/comparison/components/TargetOnlySection.vue'

describe('TargetOnlySection — secondary/collapsed', () => {
  it('is wrapped in cw-secondary-section', () => {
    const w = mount(TargetOnlySection, {
      props: {
        items: [{ target_product: { id: 202, name: 'T', price: null, currency: null, product_url: null }, target_category: null }],
      },
    })
    expect(w.find('.cw-secondary-section').exists()).toBe(true)
  })

  it('uses details element (collapsed by default)', () => {
    const w = mount(TargetOnlySection, {
      props: { items: [] },
    })
    expect(w.find('details').exists()).toBe(true)
    // Not open by default
    expect(w.find('details').attributes('open')).toBeUndefined()
  })

  it('renders item count badge', () => {
    const items = [
      { target_product: { id: 200, name: 'A', price: null, currency: null, product_url: null }, target_category: null },
      { target_product: { id: 201, name: 'B', price: null, currency: null, product_url: null }, target_category: null },
    ]
    const w = mount(TargetOnlySection, { props: { items } })
    expect(w.find('.badge-tgt').text()).toBe('2')
  })
})

// ---------------------------------------------------------------------------
// RFC-016 v2 — Commit 2: category items show no URL subtitle
// ---------------------------------------------------------------------------

describe('ComparisonControlRail — no URL subtitle in category list', () => {
  it('renders category names without URL meta text', () => {
    const w = mount(ComparisonControlRail, {
      props: {
        targetStores:      [],
        targetStoreId:     null,
        categories:        refCats,
        loadingCategories: false,
        activeCategoryId:  null,
        canCompare:        false,
        comparing:         false,
        statusText:        '',
      },
    })
    // Category URLs must NOT appear as visible text
    expect(w.text()).not.toContain('https://a.com')
    // But names still visible
    expect(w.text()).toContain('Ковзани')
  })
})

describe('ReferenceCategoryList — plain names, no URL subtitle', () => {
  it('renders only the category name without URL', () => {
    const w = mount(ReferenceCategoryList, {
      props: { categories: refCats, activeCategoryId: null, loading: false },
    })
    expect(w.text()).not.toContain('https://a.com')
    expect(w.text()).not.toContain('Без URL')
    expect(w.text()).toContain('Ковзани')
  })
})

// ---------------------------------------------------------------------------
// RFC-016 v2 — Commit 3: context strip clickable chips
// ---------------------------------------------------------------------------

describe('ComparisonSummaryBar — clickable context strip', () => {
  it('renders a link chip for ref category when cat.url is present', () => {
    const catWithUrl = { ...refCats[0], url: 'https://shop.com/skates' }
    const w = mount(ComparisonSummaryBar, {
      props: { result: comparisonResult, comparing: false, errorText: null, referenceCategory: catWithUrl, targetStore: null },
    })
    const link = w.find('a.cw-context-chip--link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('https://shop.com/skates')
    expect(link.text()).toBe('Ковзани')
  })

  it('renders a plain chip for ref category when cat.url is null', () => {
    const catNoUrl = { ...refCats[0], url: null }
    const w = mount(ComparisonSummaryBar, {
      props: { result: comparisonResult, comparing: false, errorText: null, referenceCategory: catNoUrl, targetStore: null },
    })
    // No anchor link
    expect(w.find('a.cw-context-chip--link').exists()).toBe(false)
    // But chip still visible
    expect(w.find('span.cw-context-chip').exists()).toBe(true)
    expect(w.text()).toContain('Ковзани')
  })

  it('renders a link chip for target store when base_url is present', () => {
    const storeWithUrl = { ...tgtStore, base_url: 'https://hockeyworld.ua' }
    const w = mount(ComparisonSummaryBar, {
      props: { result: comparisonResult, comparing: false, errorText: null, referenceCategory: null, targetStore: storeWithUrl },
    })
    const links = w.findAll('a.cw-context-chip--link')
    const storeLink = links.find(l => l.text() === 'hockeyworld')
    expect(storeLink).toBeDefined()
    expect(storeLink!.attributes('href')).toBe('https://hockeyworld.ua')
  })

  it('renders a plain chip for target store when base_url is null', () => {
    const storeNoUrl = { ...tgtStore, base_url: null }
    const w = mount(ComparisonSummaryBar, {
      props: { result: comparisonResult, comparing: false, errorText: null, referenceCategory: null, targetStore: storeNoUrl },
    })
    expect(w.find('a.cw-context-chip--link').exists()).toBe(false)
    expect(w.text()).toContain('hockeyworld')
  })
})

// ---------------------------------------------------------------------------
// RFC-016 v2 — Commit 4: section collapse state
// ---------------------------------------------------------------------------

import ComparisonCollapsibleSection from '@/pages/comparison/components/ComparisonCollapsibleSection.vue'

describe('useComparisonPage — section collapse state (Commit 4)', () => {
  it('all sections start collapsed (expanded=false)', () => {
    const p = useComparisonPage()
    expect(p.sectionExpanded.value.autoSuggestions).toBe(false)
    expect(p.sectionExpanded.value.candidateGroups).toBe(false)
    expect(p.sectionExpanded.value.referenceOnly).toBe(false)
  })

  it('toggleSection expands a collapsed section', () => {
    const p = useComparisonPage()
    p.toggleSection('autoSuggestions')
    expect(p.sectionExpanded.value.autoSuggestions).toBe(true)
  })

  it('toggleSection collapses an expanded section', () => {
    const p = useComparisonPage()
    p.toggleSection('candidateGroups')
    expect(p.sectionExpanded.value.candidateGroups).toBe(true)
    p.toggleSection('candidateGroups')
    expect(p.sectionExpanded.value.candidateGroups).toBe(false)
  })

  it('sections reset to collapsed after a new compare', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()

    // Expand sections manually
    p.toggleSection('autoSuggestions')
    p.toggleSection('referenceOnly')
    expect(p.sectionExpanded.value.autoSuggestions).toBe(true)

    // Compare resets them
    await p.compare()
    expect(p.sectionExpanded.value.autoSuggestions).toBe(false)
    expect(p.sectionExpanded.value.referenceOnly).toBe(false)
    expect(p.sectionExpanded.value.candidateGroups).toBe(false)
  })
})

describe('ComparisonCollapsibleSection', () => {
  it('renders title and badge', () => {
    const w = mount(ComparisonCollapsibleSection, {
      props: { title: '🔍 Авто', count: 3, expanded: false },
    })
    expect(w.text()).toContain('Авто')
    expect(w.find('.badge').text()).toBe('3')
  })

  it('hides content when expanded=false', () => {
    const w = mount(ComparisonCollapsibleSection, {
      props: { title: 'Test', count: 1, expanded: false },
      slots: { default: '<div class="inner-content">content</div>' },
    })
    // v-show makes it invisible but still in DOM
    const body = w.find('.cw-collapsible-body')
    expect(body.isVisible()).toBe(false)
  })

  it('shows content when expanded=true', () => {
    const w = mount(ComparisonCollapsibleSection, {
      props: { title: 'Test', count: 1, expanded: true },
      slots: { default: '<div class="inner-content">content</div>' },
    })
    expect(w.find('.cw-collapsible-body').isVisible()).toBe(true)
    expect(w.text()).toContain('content')
  })

  it('emits toggle when header button is clicked', async () => {
    const w = mount(ComparisonCollapsibleSection, {
      props: { title: 'Test', count: 2, expanded: false },
    })
    await w.find('.cw-collapsible-header').trigger('click')
    expect(w.emitted('toggle')).toBeTruthy()
    expect(w.emitted('toggle')).toHaveLength(1)
  })

  it('has aria-expanded=false when collapsed', () => {
    const w = mount(ComparisonCollapsibleSection, {
      props: { title: 'Test', count: 1, expanded: false },
    })
    expect(w.find('.cw-collapsible-header').attributes('aria-expanded')).toBe('false')
  })

  it('has aria-expanded=true when expanded', () => {
    const w = mount(ComparisonCollapsibleSection, {
      props: { title: 'Test', count: 1, expanded: true },
    })
    expect(w.find('.cw-collapsible-header').attributes('aria-expanded')).toBe('true')
  })
})

// ---------------------------------------------------------------------------
// RFC-016 v2 — Commit 6: icon-only action buttons with tooltips
// ---------------------------------------------------------------------------

import CandidateGroupCard from '@/pages/comparison/components/CandidateGroupCard.vue'

describe('CandidateGroupCard — icon-only actions (Commit 6)', () => {
  const group = comparisonResult.candidate_groups[0]

  it('renders icon-only confirm button with title tooltip', () => {
    const w = mount(CandidateGroupCard, {
      props: { group, decisionInProgressKey: null },
    })
    const confirmBtns = w.findAll('button.btn-icon-action.confirm')
    expect(confirmBtns.length).toBeGreaterThan(0)
    expect(confirmBtns[0].attributes('title')).toContain('Прийняти')
    // No large text, just the icon
    expect(confirmBtns[0].text().trim()).toBe('✔')
  })

  it('renders icon-only reject button with title tooltip', () => {
    const w = mount(CandidateGroupCard, {
      props: { group, decisionInProgressKey: null },
    })
    const rejectBtns = w.findAll('button.btn-icon-action.reject')
    expect(rejectBtns.length).toBeGreaterThan(0)
    expect(rejectBtns[0].attributes('title')).toContain('Відхилити')
    expect(rejectBtns[0].text().trim()).toBe('✖')
  })

  it('renders pick trigger in the header row', () => {
    const w = mount(CandidateGroupCard, {
      props: { group, decisionInProgressKey: null },
    })
    const refRow = w.find('.cw-ref-row')
    expect(refRow.find('button.btn-icon-action.pick').exists()).toBe(true)
  })

  it('emits open-picker when pick trigger clicked', async () => {
    const w = mount(CandidateGroupCard, {
      props: { group, decisionInProgressKey: null },
    })
    await w.find('.cw-ref-row .btn-icon-action.pick').trigger('click')
    expect(w.emitted('open-picker')).toBeTruthy()
    expect(w.emitted('open-picker')![0][0]).toEqual(group.reference_product)
  })
})

// ---------------------------------------------------------------------------
// Commit 8 — Regression: pre-compare placeholder
// ---------------------------------------------------------------------------

import ComparisonWorkspacePlaceholder from '@/pages/comparison/components/ComparisonWorkspacePlaceholder.vue'

describe('ComparisonWorkspacePlaceholder', () => {
  it('renders placeholder title and body text', () => {
    const w = mount(ComparisonWorkspacePlaceholder, {
      props: { canCompare: false },
    })
    expect(w.text()).toContain('Готово до порівняння')
    expect(w.text()).toContain('референсну категорію')
    expect(w.text()).toContain('Порівняти')
  })

  it('shows ready hint when canCompare=true', () => {
    const w = mount(ComparisonWorkspacePlaceholder, {
      props: { canCompare: true },
    })
    expect(w.find('.cw-placeholder-hint').exists()).toBe(true)
    expect(w.text()).toContain('Усе готово')
  })

  it('does NOT show ready hint when canCompare=false', () => {
    const w = mount(ComparisonWorkspacePlaceholder, {
      props: { canCompare: false },
    })
    expect(w.find('.cw-placeholder-hint').exists()).toBe(false)
  })

  it('has role=status for screen readers', () => {
    const w = mount(ComparisonWorkspacePlaceholder, {
      props: { canCompare: false },
    })
    expect(w.find('[role="status"]').exists()).toBe(true)
  })
})

describe('useComparisonPage — pre-compare placeholder state (Commit 3)', () => {
  it('comparisonWorkspaceState is idle on first mount', () => {
    const p = useComparisonPage()
    expect(p.comparisonWorkspaceState.value).toBe('idle')
  })

  it('comparisonWorkspaceState remains idle after store load until compare triggered', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    // Ready to compare but not yet compared
    expect(p.canCompare.value).toBe(true)
    expect(p.comparisonWorkspaceState.value).toBe('idle')
  })

  it('comparisonWorkspaceState transitions idle→comparing→review on successful compare', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()

    const comparePromise = p.compare()
    // Mid-flight: state should be comparing
    expect(p.comparisonWorkspaceState.value).toBe('comparing')
    await comparePromise

    expect(p.comparisonWorkspaceState.value).toBe('review')
  })

  it('comparisonWorkspaceState transitions to empty when result has no review items', async () => {
    vi.mocked(compApi.runComparison).mockResolvedValue({
      confirmed_matches: [],
      candidate_groups: [],
      reference_only: [],
      target_only: [],
      summary: { candidate_groups: 0, reference_only: 0, target_only: 0 },
    })
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    expect(p.comparisonWorkspaceState.value).toBe('empty')
  })

  it('comparisonWorkspaceState transitions to error on compare failure', async () => {
    vi.mocked(compApi.runComparison).mockRejectedValue(new Error('timeout'))
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()

    expect(p.comparisonWorkspaceState.value).toBe('error')
  })

  it('comparisonWorkspaceState resets to idle on subsequent compare start', async () => {
    const p = useComparisonPage()
    await p.loadStores()
    await flushPromises()
    await p.selectRefCategory(10)
    await flushPromises()
    await p.compare()
    expect(p.comparisonWorkspaceState.value).toBe('review')

    // Second compare — clears result first, then starts fetching
    const comparePromise = p.compare()
    expect(p.comparisonWorkspaceState.value).toBe('comparing')
    await comparePromise
    expect(p.comparisonWorkspaceState.value).toBe('review')
  })
})

// ---------------------------------------------------------------------------
// Commit 8 — Regression: category product counts in control rail
// ---------------------------------------------------------------------------

describe('ComparisonControlRail — category product count badges (Commit 2)', () => {
  const catsWithCounts = [
    { id: 10, store_id: 1, name: 'Ковзани', normalized_name: null, url: null, external_id: null, updated_at: null, product_count: 42 },
    { id: 11, store_id: 1, name: 'Шлеми',  normalized_name: null, url: null, external_id: null, updated_at: null, product_count: 0  },
    { id: 12, store_id: 1, name: 'Рукавиці', normalized_name: null, url: null, external_id: null, updated_at: null, product_count: 7 },
  ]

  const baseProps = {
    targetStores:      [] as import('@/types/store').StoreSummary[],
    targetStoreId:     null,
    categories:        catsWithCounts,
    loadingCategories: false,
    activeCategoryId:  null,
    canCompare:        false,
    comparing:         false,
    statusText:        '',
  }

  it('renders a count badge for categories with product_count', () => {
    const w = mount(ComparisonControlRail, { props: baseProps })
    const badges = w.findAll('.cw-cat-count')
    expect(badges.length).toBe(3)
    expect(badges[0].text()).toBe('42')
    expect(badges[2].text()).toBe('7')
  })

  it('marks zero-count category with cw-cat-count--empty class', () => {
    const w = mount(ComparisonControlRail, { props: baseProps })
    const badges = w.findAll('.cw-cat-count')
    // Second category has count=0
    expect(badges[1].classes()).toContain('cw-cat-count--empty')
    expect(badges[0].classes()).not.toContain('cw-cat-count--empty')
  })

  it('does NOT render count badge when product_count is absent', () => {
    const catsNoCounts = refCats  // fixture without product_count
    const w = mount(ComparisonControlRail, {
      props: { ...baseProps, categories: catsNoCounts },
    })
    expect(w.findAll('.cw-cat-count')).toHaveLength(0)
  })

  it('shows tooltip on zero-count badge indicating no products', () => {
    const w = mount(ComparisonControlRail, { props: baseProps })
    const badges = w.findAll('.cw-cat-count')
    expect(badges[1].attributes('title')).toContain('Немає товарів')
  })

  it('shows product count in tooltip for non-zero badge', () => {
    const w = mount(ComparisonControlRail, { props: baseProps })
    const badges = w.findAll('.cw-cat-count')
    expect(badges[0].attributes('title')).toContain('42')
  })
})

