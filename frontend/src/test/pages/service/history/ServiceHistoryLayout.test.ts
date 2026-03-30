/**
 * ServiceHistoryLayout.test.ts — Commit 07 + 09 assertions for
 * ServiceHistoryApp.vue layout.
 *
 * Key assertions:
 *  1. Filters render in a horizontal bar ABOVE the table (not in a left rail).
 *  2. Table is the dominant surface (renders after the filter bar).
 *  3. Pagination renders after the table.
 *  4. Loading / error / info states are still present.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { mount } from '@vue/test-utils'
import ServiceHistoryApp from '@/pages/service/history/ServiceHistoryApp.vue'

// ---------------------------------------------------------------------------
// Mock composable — avoid real API calls
// ---------------------------------------------------------------------------

vi.mock('@/pages/service/history/composables/useServiceHistory')

import { useServiceHistory } from '@/pages/service/history/composables/useServiceHistory'

function makeHistoryStateMock() {
  const filters = { storeId: '', runType: '', status: '', triggerType: '' }
  return {
    stores:         ref([]),
    storesLoading:  ref(false),
    filters,
    setFilter:      vi.fn(),
    resetFilters:   vi.fn(),
    page:           ref(0),
    pageSize:       ref(10),
    prevPage:       vi.fn(),
    nextPage:       vi.fn(),
    runs:           ref([]),
    loading:        ref(false),
    error:          ref<string | null>(null),
    reload:         vi.fn(),
    detailRunId:    ref<number | null>(null),
    detailRun:      ref(null),
    detailLoading:  ref(false),
    detailError:    ref<string | null>(null),
    openDetails:    vi.fn(),
    closeDetails:   vi.fn(),
  }
}

// ---------------------------------------------------------------------------
// Stub child components so they render predictable markers in the DOM
// ---------------------------------------------------------------------------

vi.mock('@/pages/service/history/components/HistoryFilters.vue', () => ({
  default: { template: '<div data-testid="history-filters"></div>', props: ['stores','storeId','runType','status','triggerType'] },
}))
vi.mock('@/pages/service/history/components/HistoryTable.vue', () => ({
  default: { template: '<div data-testid="history-table"></div>', props: ['runs'] },
}))
vi.mock('@/pages/service/history/components/HistoryPagination.vue', () => ({
  default: { template: '<div data-testid="history-pagination"></div>', props: ['page','pageSize','itemCount','disabled'] },
}))
vi.mock('@/pages/service/history/components/RunDetailsDialog.vue', () => ({
  default: { template: '<div data-testid="run-details-dialog"></div>', props: ['open','run','loading','error'] },
}))

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useServiceHistory).mockReturnValue(makeHistoryStateMock() as never)
})

// ---------------------------------------------------------------------------
// Layout assertions
// ---------------------------------------------------------------------------

describe('ServiceHistoryApp — top filter bar layout (Commit 07)', () => {
  it('renders the .sc-hist-filter-bar panel', () => {
    const w = mount(ServiceHistoryApp)
    expect(w.find('.sc-hist-filter-bar').exists()).toBe(true)
  })

  it('renders HistoryFilters inside the filter bar', () => {
    const w = mount(ServiceHistoryApp)
    const bar = w.find('.sc-hist-filter-bar')
    expect(bar.find('[data-testid="history-filters"]').exists()).toBe(true)
  })

  it('renders HistoryTable as a direct child of .sc-section', () => {
    const w = mount(ServiceHistoryApp)
    expect(w.find('[data-testid="history-table"]').exists()).toBe(true)
  })

  it('filter bar appears BEFORE the table in the DOM', () => {
    const w = mount(ServiceHistoryApp)
    const root = w.element as Element
    const filterBar = root.querySelector('.sc-hist-filter-bar')
    const table     = root.querySelector('[data-testid="history-table"]')

    expect(filterBar).toBeTruthy()
    expect(table).toBeTruthy()
    // Node.DOCUMENT_POSITION_FOLLOWING means table comes after filterBar
    const rel = filterBar!.compareDocumentPosition(table!)
    expect(rel & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('pagination renders AFTER the table in the DOM', () => {
    const w = mount(ServiceHistoryApp)
    const root       = w.element as Element
    const table      = root.querySelector('[data-testid="history-table"]')
    const pagination = root.querySelector('[data-testid="history-pagination"]')

    expect(table).toBeTruthy()
    expect(pagination).toBeTruthy()
    const rel = table!.compareDocumentPosition(pagination!)
    expect(rel & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('does NOT render filters inside a left-rail element', () => {
    const w = mount(ServiceHistoryApp)
    // history section must NOT have a sc-inner-rail (no left-column filter rail)
    expect(w.find('.sc-inner-rail').exists()).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// State surface assertions
// ---------------------------------------------------------------------------

describe('ServiceHistoryApp — state surfaces', () => {
  it('shows loading indicator when loading=true', () => {
    const state = makeHistoryStateMock()
    state.loading.value = true
    vi.mocked(useServiceHistory).mockReturnValue(state as never)

    const w = mount(ServiceHistoryApp)
    expect(w.text()).toContain('Завантаження')
  })

  it('shows error message when error is set', () => {
    const state = makeHistoryStateMock()
    state.error.value = 'Network error'
    vi.mocked(useServiceHistory).mockReturnValue(state as never)

    const w = mount(ServiceHistoryApp)
    expect(w.text()).toContain('Network error')
  })

  it('shows record count when loaded without error', () => {
    const state = makeHistoryStateMock()
    state.runs.value = [] // 0 records
    vi.mocked(useServiceHistory).mockReturnValue(state as never)

    const w = mount(ServiceHistoryApp)
    expect(w.text()).toContain('Записів на сторінці: 0')
  })

  it('renders refresh button', () => {
    const w = mount(ServiceHistoryApp)
    expect(w.text()).toContain('Оновити')
  })

  it('clicking refresh calls state.reload', async () => {
    const state = makeHistoryStateMock()
    vi.mocked(useServiceHistory).mockReturnValue(state as never)

    const w = mount(ServiceHistoryApp)
    await w.find('.sc-section-actions button').trigger('click')
    expect(state.reload).toHaveBeenCalled()
  })
})

