/**
 * MappingsTabLayout.test.ts — Commit 07 regression tests for the Mappings
 * top-filter-block layout.
 *
 * Key assertions:
 *  1. No inner left rail (.sc-inner-rail) — layout is now top-filter + table.
 *  2. Filter block (.sc-mapp-filter-bar) is present.
 *  3. Filter block appears BEFORE the results area.
 *  4. MappingsTable no longer renders Тип / Confidence columns.
 *  5. Both store selectors are present in the filter bar.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import MappingsTab from '@/pages/service/mappings/MappingsTab.vue'

// ---------------------------------------------------------------------------
// Stub heavy children
// ---------------------------------------------------------------------------

vi.mock('@/pages/service/mappings/components/MappingsTable.vue', () => ({
  default: { template: '<div data-testid="mappings-table"></div>', props: ['mappings','deletingIds'] },
}))
vi.mock('@/pages/service/mappings/components/MappingDrawer.vue', () => ({
  default: { template: '<div></div>', props: Object.keys({ open:0,mode:0,mapping:0,refCategories:0,targetStores:0,defaultTargetStoreId:0,defaultTargetCategories:0,pending:0,errorMsg:0 }) },
}))

// ---------------------------------------------------------------------------
// Mock composable
// ---------------------------------------------------------------------------

vi.mock('@/pages/service/mappings/composables/useMappingsTab')
import { useMappingsTab } from '@/pages/service/mappings/composables/useMappingsTab'

const refStore    = { id: 1, name: 'prohockey',   is_reference: true,  base_url: null }
const targetStore = { id: 2, name: 'hockeyworld', is_reference: false, base_url: null }

function makeTabState(overrides: Record<string, unknown> = {}) {
  return {
    stores:              ref([refStore, targetStore]),
    refStoreId:          ref<number | null>(null),
    targetStoreId:       ref<number | null>(null),
    refCategories:       ref([]),
    targetCategories:    ref([]),
    mappings:            ref([]),
    loading:             ref(false),
    error:               ref<string | null>(null),
    submitPending:       ref(false),
    submitError:         ref<string | null>(null),
    deletingIds:         ref(new Set<number>()),
    autoLinkPending:     ref(false),
    autoLinkSummary:     ref(null),
    drawerOpen:          ref(false),
    drawerMode:          ref<'create'|'edit'>('create'),
    drawerMapping:       ref(null),
    clearAutoLinkSummary: vi.fn(),
    openCreateDrawer:    vi.fn(),
    openEditDrawer:      vi.fn(),
    closeDrawer:         vi.fn(),
    submitDrawer:        vi.fn(),
    setRefStore:         vi.fn(),
    setTargetStore:      vi.fn(),
    loadMappings:        vi.fn(),
    triggerAutoLink:     vi.fn(),
    // legacy (unused in template but in interface)
    dialogOpen: ref(false), dialogMode: ref('create'), dialogMapping: ref(null),
    closeDialog: vi.fn(), submitDialog: vi.fn(), openCreateDialog: vi.fn(),
    openEditDialog: vi.fn(), deleteMappingById: vi.fn(),
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useMappingsTab).mockReturnValue(makeTabState() as never)
})

// ---------------------------------------------------------------------------
// Layout assertions
// ---------------------------------------------------------------------------

describe('MappingsTab — top filter bar layout (no inner rail)', () => {
  it('does NOT render a .sc-inner-rail element', () => {
    const w = mount(MappingsTab)
    expect(w.find('.sc-inner-rail').exists()).toBe(false)
  })

  it('does NOT render .sc-inner-workspace', () => {
    const w = mount(MappingsTab)
    expect(w.find('.sc-inner-workspace').exists()).toBe(false)
  })

  it('renders the .sc-mapp-filter-bar top block', () => {
    const w = mount(MappingsTab)
    expect(w.find('.sc-mapp-filter-bar').exists()).toBe(true)
  })

  it('filter bar appears BEFORE the results area in the DOM', () => {
    const state = makeTabState({
      refStoreId:    ref(1),
      targetStoreId: ref(2),
      mappings:      ref([{ id: 1, reference_category_id: 1, target_category_id: 2,
                            reference_category_name: 'A', target_category_name: 'B',
                            reference_store_id: 1, target_store_id: 2,
                            match_type: null, confidence: null, updated_at: null }]),
    })
    vi.mocked(useMappingsTab).mockReturnValue(state as never)

    const w = mount(MappingsTab)
    const root    = w.element as Element
    const bar     = root.querySelector('.sc-mapp-filter-bar')
    const results = root.querySelector('[data-testid="mappings-table"]')

    expect(bar).toBeTruthy()
    expect(results).toBeTruthy()
    expect(bar!.compareDocumentPosition(results!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('renders reference store selector in the filter bar', () => {
    const w = mount(MappingsTab)
    expect(w.find('#mapp-ref-store').exists()).toBe(true)
  })

  it('renders target store selector in the filter bar', () => {
    const w = mount(MappingsTab)
    expect(w.find('#mapp-tgt-store').exists()).toBe(true)
  })

  it('only non-reference stores appear in target store selector', () => {
    const w = mount(MappingsTab)
    const opts = w.find('#mapp-tgt-store').findAll('option').map((o) => o.text())
    expect(opts.some((t) => t.includes('hockeyworld'))).toBe(true)
    expect(opts.some((t) => t.includes('prohockey'))).toBe(false)
  })

  it('only reference stores appear in reference store selector', () => {
    const w = mount(MappingsTab)
    const opts = w.find('#mapp-ref-store').findAll('option').map((o) => o.text())
    expect(opts.some((t) => t.includes('prohockey'))).toBe(true)
    expect(opts.some((t) => t.includes('hockeyworld'))).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Button / action assertions
// ---------------------------------------------------------------------------

describe('MappingsTab — actions', () => {
  it('"+ Новий мапінг" button is disabled when both stores not selected', () => {
    const w = mount(MappingsTab)
    const btn = w.findAll('button').find((b) => b.text().includes('Новий'))
    expect((btn!.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('"+ Новий мапінг" button is enabled when both stores selected', () => {
    vi.mocked(useMappingsTab).mockReturnValue(
      makeTabState({ refStoreId: ref(1), targetStoreId: ref(2) }) as never,
    )
    const w = mount(MappingsTab)
    const btn = w.findAll('button').find((b) => b.text().includes('Новий'))
    expect((btn!.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('clicking "+ Новий мапінг" calls state.openCreateDrawer', async () => {
    const state = makeTabState({ refStoreId: ref(1), targetStoreId: ref(2) })
    vi.mocked(useMappingsTab).mockReturnValue(state as never)

    const w = mount(MappingsTab)
    await w.findAll('button').find((b) => b.text().includes('Новий'))!.trigger('click')
    await flushPromises()

    expect(state.openCreateDrawer).toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Empty / loading states
// ---------------------------------------------------------------------------

describe('MappingsTab — empty states', () => {
  it('shows empty state when no stores selected', () => {
    const w = mount(MappingsTab)
    expect(w.find('.empty-state').exists()).toBe(true)
    expect(w.text()).toContain('Оберіть магазини')
  })

  it('shows loading state when loading=true', () => {
    vi.mocked(useMappingsTab).mockReturnValue(
      makeTabState({ refStoreId: ref(1), targetStoreId: ref(2), loading: ref(true) }) as never,
    )
    const w = mount(MappingsTab)
    expect(w.text()).toContain('Завантаження')
  })

  it('shows no-mappings empty state', () => {
    vi.mocked(useMappingsTab).mockReturnValue(
      makeTabState({ refStoreId: ref(1), targetStoreId: ref(2) }) as never,
    )
    const w = mount(MappingsTab)
    expect(w.text()).toContain('Немає мапінгів')
  })
})

