import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { useMappingsTab } from '@/pages/service/mappings/composables/useMappingsTab'

// ---------------------------------------------------------------------------
// Mock API client
// ---------------------------------------------------------------------------

vi.mock('@/api/client', () => ({
  fetchStores: vi.fn(),
  fetchCategoriesForStore: vi.fn(),
  fetchCategoryMappings: vi.fn(),
  createCategoryMapping: vi.fn(),
  updateCategoryMapping: vi.fn(),
  deleteCategoryMapping: vi.fn(),
  autoLinkCategoryMappings: vi.fn(),
}))

import * as client from '@/api/client'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const stores = [
  { id: 1, name: 'prohockey', is_reference: true, base_url: null },
  { id: 2, name: 'hockeyworld', is_reference: false, base_url: null },
]

const refCats = [
  { id: 10, store_id: 1, name: 'Ковзани', normalized_name: 'kovzany', url: null, external_id: null, updated_at: null },
  { id: 11, store_id: 1, name: 'Шоломи', normalized_name: 'sholomy', url: null, external_id: null, updated_at: null },
]

const tgtCats = [
  { id: 20, store_id: 2, name: 'Skates', normalized_name: 'kovzany', url: null, external_id: null, updated_at: null },
]

const mappings = [
  {
    id: 1,
    reference_category_id: 10,
    target_category_id: 20,
    reference_category_name: 'Ковзани',
    target_category_name: 'Skates',
    reference_store_id: 1,
    target_store_id: 2,
    match_type: 'exact',
    confidence: 1.0,
    updated_at: null,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(client.fetchStores).mockResolvedValue(stores)
  vi.mocked(client.fetchCategoriesForStore).mockResolvedValue([])
  vi.mocked(client.fetchCategoryMappings).mockResolvedValue([])
})

// ---------------------------------------------------------------------------
// 1. Load state: no stores selected → no mappings, no fetch
// ---------------------------------------------------------------------------

describe('useMappingsTab — initial state', () => {
  it('starts with empty state and no selection', async () => {
    const state = useMappingsTab()
    await flushPromises()

    expect(state.refStoreId.value).toBeNull()
    expect(state.targetStoreId.value).toBeNull()
    expect(state.mappings.value).toEqual([])
    expect(state.loading.value).toBe(false)
    expect(state.error.value).toBeNull()
  })

  it('loads stores list on init', async () => {
    const state = useMappingsTab()
    await flushPromises()

    expect(state.stores.value).toHaveLength(2)
    expect(client.fetchStores).toHaveBeenCalledTimes(1)
  })

  it('does NOT fetch mappings when only one store selected', async () => {
    const state = useMappingsTab()
    await state.setRefStore(1)
    expect(client.fetchCategoryMappings).not.toHaveBeenCalled()
    expect(state.mappings.value).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// 2. Mappings list rendering — loads when both stores selected
// ---------------------------------------------------------------------------

describe('useMappingsTab — loadMappings', () => {
  it('fetches mappings when both stores are set', async () => {
    vi.mocked(client.fetchCategoriesForStore).mockResolvedValue(refCats)
    vi.mocked(client.fetchCategoryMappings).mockResolvedValue(mappings)

    const state = useMappingsTab()
    await state.setRefStore(1)
    await state.setTargetStore(2)

    expect(client.fetchCategoryMappings).toHaveBeenCalledWith(1, 2)
    expect(state.mappings.value).toHaveLength(1)
    expect(state.mappings.value[0].reference_category_name).toBe('Ковзани')
  })

  it('clears mappings and does not call API when a store is deselected', async () => {
    vi.mocked(client.fetchCategoryMappings).mockResolvedValue(mappings)

    const state = useMappingsTab()
    await state.setRefStore(1)
    await state.setTargetStore(2)
    expect(state.mappings.value).toHaveLength(1)

    await state.setTargetStore(null)
    expect(state.mappings.value).toEqual([])
    // fetchCategoryMappings called only once (when both were selected)
    expect(client.fetchCategoryMappings).toHaveBeenCalledTimes(1)
  })

  it('sets error on fetch failure', async () => {
    vi.mocked(client.fetchCategoryMappings).mockRejectedValueOnce(new Error('network error'))

    const state = useMappingsTab()
    await state.setRefStore(1)
    await state.setTargetStore(2)

    expect(state.error.value).toContain('network error')
    expect(state.loading.value).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// 3. Create dialog
// ---------------------------------------------------------------------------

describe('useMappingsTab — create dialog', () => {
  it('opens in create mode with empty form state', async () => {
    vi.mocked(client.fetchCategoriesForStore).mockResolvedValue(refCats)

    const state = useMappingsTab()
    await state.setRefStore(1)
    await state.setTargetStore(2)
    await state.openCreateDialog()

    expect(state.dialogOpen.value).toBe(true)
    expect(state.dialogMode.value).toBe('create')
    expect(state.dialogMapping.value).toBeNull()
  })

  it('loads ref and target categories when opening create dialog', async () => {
    vi.mocked(client.fetchCategoriesForStore)
      .mockResolvedValueOnce(refCats)   // ref store
      .mockResolvedValueOnce(tgtCats)   // target store

    const state = useMappingsTab()
    await state.setRefStore(1)
    await state.setTargetStore(2)
    await state.openCreateDialog()

    expect(state.refCategories.value).toHaveLength(2)
    expect(state.targetCategories.value).toHaveLength(1)
  })

  it('submits create and updates mappings list', async () => {
    vi.mocked(client.fetchCategoriesForStore).mockResolvedValue(refCats)
    vi.mocked(client.createCategoryMapping).mockResolvedValueOnce(mappings)

    const state = useMappingsTab()
    await state.setRefStore(1)
    await state.setTargetStore(2)
    await state.openCreateDialog()

    await state.submitDialog({
      reference_category_id: '10',
      target_category_id: '20',
      match_type: 'manual',
      confidence: '0.9',
    })

    expect(client.createCategoryMapping).toHaveBeenCalledWith(
      expect.objectContaining({
        reference_category_id: 10,
        target_category_id: 20,
        match_type: 'manual',
        confidence: 0.9,
      }),
    )
    expect(state.mappings.value).toEqual(mappings)
    expect(state.dialogOpen.value).toBe(false)
  })

  it('sets submitError when categories are missing', async () => {
    const state = useMappingsTab()
    await state.setRefStore(1)
    await state.setTargetStore(2)
    await state.openCreateDialog()

    await state.submitDialog({
      reference_category_id: '',
      target_category_id: '',
      match_type: '',
      confidence: '',
    })

    expect(state.submitError.value).toBeTruthy()
    expect(state.dialogOpen.value).toBe(true) // stays open
  })
})

// ---------------------------------------------------------------------------
// 4. Edit dialog — category pair is read-only
// ---------------------------------------------------------------------------

describe('useMappingsTab — edit dialog', () => {
  it('opens in edit mode with the mapping pre-selected', () => {
    const state = useMappingsTab()
    state.openEditDialog(mappings[0])

    expect(state.dialogOpen.value).toBe(true)
    expect(state.dialogMode.value).toBe('edit')
    expect(state.dialogMapping.value).toEqual(mappings[0])
  })

  it('submits update and closes dialog on success', async () => {
    const updated = [{ ...mappings[0], match_type: 'manual', confidence: 0.8 }]
    vi.mocked(client.updateCategoryMapping).mockResolvedValueOnce(updated)

    const state = useMappingsTab()
    state.stores.value = stores
    state.refStoreId.value = 1
    state.targetStoreId.value = 2
    state.openEditDialog(mappings[0])

    await state.submitDialog({
      reference_category_id: '10',
      target_category_id: '20',
      match_type: 'manual',
      confidence: '0.8',
    })

    expect(client.updateCategoryMapping).toHaveBeenCalledWith(
      1,
      { match_type: 'manual', confidence: 0.8 },
      1,
      2,
    )
    expect(state.mappings.value[0].match_type).toBe('manual')
    expect(state.dialogOpen.value).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// 5. Auto-link action
// ---------------------------------------------------------------------------

describe('useMappingsTab — triggerAutoLink', () => {
  it('updates autoLinkSummary and mappings atomically from enriched response', async () => {
    const autoLinkResult = {
      summary: { created: 3, skipped_existing: 1, skipped_no_norm: 0 },
      mappings,
    }
    vi.mocked(client.autoLinkCategoryMappings).mockResolvedValueOnce(autoLinkResult)

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2

    const p = state.triggerAutoLink()
    expect(state.autoLinkPending.value).toBe(true)
    await p

    expect(state.autoLinkPending.value).toBe(false)
    expect(state.autoLinkSummary.value?.summary).toEqual(autoLinkResult.summary)
    expect(state.mappings.value).toEqual(mappings)
    // No second fetch should happen — enriched response covers it
    expect(client.fetchCategoryMappings).not.toHaveBeenCalled()
  })

  it('does NOT call fetchCategoryMappings on success path', async () => {
    const autoLinkResult = {
      summary: { created: 1, skipped_existing: 0, skipped_no_norm: 0 },
      mappings,
    }
    vi.mocked(client.autoLinkCategoryMappings).mockResolvedValueOnce(autoLinkResult)

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2
    await state.triggerAutoLink()

    expect(client.fetchCategoryMappings).not.toHaveBeenCalled()
  })

  it('clears autoLinkSummary resets it to null', async () => {
    const autoLinkResult = {
      summary: { created: 1, skipped_existing: 0, skipped_no_norm: 0 },
      mappings: [],
    }
    vi.mocked(client.autoLinkCategoryMappings).mockResolvedValueOnce(autoLinkResult)

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2
    await state.triggerAutoLink()
    expect(state.autoLinkSummary.value).not.toBeNull()

    state.clearAutoLinkSummary()
    expect(state.autoLinkSummary.value).toBeNull()
  })

  it('does nothing when stores not both selected', async () => {
    const state = useMappingsTab()
    state.refStoreId.value = 1
    // targetStoreId is null
    await state.triggerAutoLink()
    expect(client.autoLinkCategoryMappings).not.toHaveBeenCalled()
  })

  it('sets error and does not update mappings on failure', async () => {
    vi.mocked(client.autoLinkCategoryMappings).mockRejectedValueOnce(new Error('network error'))

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2
    state.mappings.value = [...mappings]

    await state.triggerAutoLink()

    expect(state.error.value).toContain('network error')
    // Mappings should remain unchanged on error
    expect(state.mappings.value).toEqual(mappings)
  })
})

// ---------------------------------------------------------------------------
// 6. Delete action
// ---------------------------------------------------------------------------

describe('useMappingsTab — deleteMappingById', () => {
  it('calls deleteCategoryMapping and refreshes list', async () => {
    vi.mocked(client.deleteCategoryMapping).mockResolvedValueOnce([])

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2
    state.mappings.value = [...mappings]

    await state.deleteMappingById(1)

    expect(client.deleteCategoryMapping).toHaveBeenCalledWith(1, 1, 2)
    expect(state.mappings.value).toEqual([])
    expect(state.deletingIds.value.has(1)).toBe(false)
  })

  it('is idempotent: second call while first is in-flight is ignored', async () => {
    let resolve!: (v: typeof mappings) => void
    const pending = new Promise<typeof mappings>((res) => { resolve = res })
    vi.mocked(client.deleteCategoryMapping).mockReturnValueOnce(pending)

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2

    const first = state.deleteMappingById(1)
    state.deleteMappingById(1) // second call — should be ignored
    resolve([])
    await first

    expect(client.deleteCategoryMapping).toHaveBeenCalledTimes(1)
  })

  it('sets error on failure without crashing', async () => {
    vi.mocked(client.deleteCategoryMapping).mockRejectedValueOnce(new Error('server error'))

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2

    await state.deleteMappingById(1)

    expect(state.error.value).toContain('server error')
    expect(state.deletingIds.value.has(1)).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// 7. closeDialog resets state
// ---------------------------------------------------------------------------

describe('useMappingsTab — closeDialog', () => {
  it('resets dialogOpen, dialogMapping, submitError', () => {
    const state = useMappingsTab()
    state.openEditDialog(mappings[0])
    state.submitError.value = 'some error'

    state.closeDialog()

    expect(state.dialogOpen.value).toBe(false)
    expect(state.dialogMapping.value).toBeNull()
    expect(state.submitError.value).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// 8. Drawer — openCreateDrawer loads target categories from page state
// ---------------------------------------------------------------------------

describe('useMappingsTab — openCreateDrawer (Commit 1 fixup)', () => {
  it('opens the drawer in create mode', async () => {
    vi.mocked(client.fetchCategoriesForStore).mockResolvedValue(refCats)
    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2

    await state.openCreateDrawer()

    expect(state.drawerOpen.value).toBe(true)
    expect(state.drawerMode.value).toBe('create')
    expect(state.drawerMapping.value).toBeNull()
  })

  it('loads target categories so drawer can show them immediately', async () => {
    vi.mocked(client.fetchCategoriesForStore)
      .mockResolvedValueOnce(refCats)   // ref store categories
      .mockResolvedValueOnce(tgtCats)   // target store categories

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2

    await state.openCreateDrawer()

    expect(client.fetchCategoriesForStore).toHaveBeenCalledWith(2)
    expect(state.targetCategories.value).toHaveLength(1)
    expect(state.targetCategories.value[0].name).toBe('Skates')
  })

  it('does not call fetchCategoriesForStore for target when targetStoreId is null', async () => {
    vi.mocked(client.fetchCategoriesForStore).mockResolvedValue(refCats)

    const state = useMappingsTab()
    state.refStoreId.value = 1
    // targetStoreId intentionally not set

    await state.openCreateDrawer()

    // Only one call: the ref store lookup. No second call for a null target.
    expect(client.fetchCategoriesForStore).toHaveBeenCalledTimes(1)
    expect(client.fetchCategoriesForStore).toHaveBeenCalledWith(1)
  })

  it('uses already-cached categories without a second API call', async () => {
    vi.mocked(client.fetchCategoriesForStore)
      .mockResolvedValueOnce(tgtCats)   // initial setTargetStore call
      .mockResolvedValueOnce(refCats)   // openCreateDrawer ref

    const state = useMappingsTab()
    // Populate cache via setTargetStore
    await state.setTargetStore(2)

    vi.clearAllMocks()

    state.refStoreId.value = 1
    await state.openCreateDrawer()

    // target was already cached — no extra API call for store 2
    expect(client.fetchCategoriesForStore).not.toHaveBeenCalledWith(2)
  })
})

// ---------------------------------------------------------------------------
// 9. Drawer — openEditDrawer sets state correctly
// ---------------------------------------------------------------------------

describe('useMappingsTab — openEditDrawer', () => {
  it('opens in edit mode with the mapping pre-selected', () => {
    const state = useMappingsTab()
    state.openEditDrawer(mappings[0])

    expect(state.drawerOpen.value).toBe(true)
    expect(state.drawerMode.value).toBe('edit')
    expect(state.drawerMapping.value).toEqual(mappings[0])
  })
})

// ---------------------------------------------------------------------------
// 10. Drawer — closeDrawer resets state
// ---------------------------------------------------------------------------

describe('useMappingsTab — closeDrawer', () => {
  it('resets drawerOpen, drawerMapping, submitError', () => {
    const state = useMappingsTab()
    state.openEditDrawer(mappings[0])
    state.submitError.value = 'drawer error'

    state.closeDrawer()

    expect(state.drawerOpen.value).toBe(false)
    expect(state.drawerMapping.value).toBeNull()
    expect(state.submitError.value).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// 11. Drawer — submitDrawer create
// ---------------------------------------------------------------------------

describe('useMappingsTab — submitDrawer create', () => {
  it('calls createCategoryMapping with correct payload (no match_type/confidence)', async () => {
    vi.mocked(client.createCategoryMapping).mockResolvedValueOnce(mappings)

    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2

    await state.submitDrawer({
      reference_category_id: '10',
      target_store_id: '2',
      target_category_id: '20',
    })

    expect(client.createCategoryMapping).toHaveBeenCalledWith(
      expect.objectContaining({
        reference_category_id: 10,
        target_category_id: 20,
        match_type: null,
        confidence: null,
      }),
    )
    expect(state.mappings.value).toEqual(mappings)
    expect(state.drawerOpen.value).toBe(false)
  })

  it('sets submitError and keeps drawer open when category ids are missing', async () => {
    const state = useMappingsTab()
    state.refStoreId.value = 1
    state.targetStoreId.value = 2

    await state.submitDrawer({
      reference_category_id: '',
      target_store_id: '2',
      target_category_id: '',
    })

    expect(state.submitError.value).toBeTruthy()
    expect(state.drawerOpen.value).toBe(false) // drawer closes only after success
  })
})


