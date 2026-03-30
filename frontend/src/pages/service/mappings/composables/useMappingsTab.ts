/**
 * useMappingsTab.ts — composable owning all Mappings tab state and actions.
 *
 * Manages:
 *  - stores list (loaded on init)
 *  - ref/target store selection with lazy category fetching
 *  - mappings list loading
 *  - create / update / delete actions
 *  - auto-link action
 *  - dialog open/close state
 *
 * Callers must NOT mutate state directly; use the exposed action functions.
 */
import { ref } from 'vue'
import type { Ref } from 'vue'
import {
  fetchStores,
  fetchCategoriesForStore,
  fetchCategoryMappings,
  createCategoryMapping,
  updateCategoryMapping,
  deleteCategoryMapping,
  autoLinkCategoryMappings,
} from '@/api/client'
import type { StoreSummary, CategorySummary } from '@/types/store'
import type { MappingRow, AutoLinkResult, MappingFormModel, DrawerFormModel } from '@/types/mappings'

// ---------------------------------------------------------------------------
// Interface
// ---------------------------------------------------------------------------

export interface MappingsTabState {
  stores: Ref<StoreSummary[]>
  refStoreId: Ref<number | null>
  targetStoreId: Ref<number | null>
  refCategories: Ref<CategorySummary[]>
  targetCategories: Ref<CategorySummary[]>

  mappings: Ref<MappingRow[]>
  loading: Ref<boolean>
  error: Ref<string | null>

  submitPending: Ref<boolean>
  submitError: Ref<string | null>
  deletingIds: Ref<Set<number>>

  autoLinkPending: Ref<boolean>
  autoLinkSummary: Ref<AutoLinkResult | null>
  clearAutoLinkSummary: () => void

  // Legacy modal state (kept for backward compat)
  dialogOpen: Ref<boolean>
  dialogMode: Ref<'create' | 'edit'>
  dialogMapping: Ref<MappingRow | null>
  closeDialog: () => void
  submitDialog: (form: MappingFormModel) => Promise<void>

  // Drawer state (Commit 04)
  drawerOpen: Ref<boolean>
  drawerMode: Ref<'create' | 'edit'>
  drawerMapping: Ref<MappingRow | null>
  openCreateDrawer: () => Promise<void>
  openEditDrawer: (mapping: MappingRow) => void
  closeDrawer: () => void
  submitDrawer: (form: DrawerFormModel) => Promise<void>

  setRefStore: (id: number | null) => Promise<void>
  setTargetStore: (id: number | null) => Promise<void>
  loadMappings: () => Promise<void>
  openCreateDialog: () => Promise<void>
  openEditDialog: (mapping: MappingRow) => void
  deleteMappingById: (mappingId: number) => Promise<void>
  triggerAutoLink: () => Promise<void>
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

export function useMappingsTab(): MappingsTabState {
  const stores = ref<StoreSummary[]>([])
  const refStoreId = ref<number | null>(null)
  const targetStoreId = ref<number | null>(null)
  const refCategories = ref<CategorySummary[]>([])
  const targetCategories = ref<CategorySummary[]>([])

  const mappings = ref<MappingRow[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const submitPending = ref(false)
  const submitError = ref<string | null>(null)
  const deletingIds = ref<Set<number>>(new Set())

  const autoLinkPending = ref(false)
  const autoLinkSummary = ref<AutoLinkResult | null>(null)

  const dialogOpen = ref(false)
  const dialogMode = ref<'create' | 'edit'>('create')
  const dialogMapping = ref<MappingRow | null>(null)

  // Drawer state (Commit 04)
  const drawerOpen = ref(false)
  const drawerMode = ref<'create' | 'edit'>('create')
  const drawerMapping = ref<MappingRow | null>(null)

  // In-process category cache: storeId → categories
  const _catCache = new Map<number, CategorySummary[]>()

  // ── Internal helpers ────────────────────────────────────────────────────

  async function _ensureCategories(storeId: number): Promise<CategorySummary[]> {
    if (_catCache.has(storeId)) return _catCache.get(storeId)!
    const cats = await fetchCategoriesForStore(storeId)
    _catCache.set(storeId, cats)
    return cats
  }

  // ── Public actions ───────────────────────────────────────────────────────

  async function loadMappings(): Promise<void> {
    if (!refStoreId.value || !targetStoreId.value) {
      mappings.value = []
      error.value = null
      return
    }
    loading.value = true
    error.value = null
    try {
      mappings.value = await fetchCategoryMappings(refStoreId.value, targetStoreId.value)
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      loading.value = false
    }
  }

  async function setRefStore(id: number | null): Promise<void> {
    refStoreId.value = id
    refCategories.value = id ? await _ensureCategories(id).catch(() => []) : []
    await loadMappings()
  }

  async function setTargetStore(id: number | null): Promise<void> {
    targetStoreId.value = id
    targetCategories.value = id ? await _ensureCategories(id).catch(() => []) : []
    await loadMappings()
  }

  async function openCreateDialog(): Promise<void> {
    // Ensure categories loaded for both selected stores
    if (refStoreId.value) {
      refCategories.value = await _ensureCategories(refStoreId.value).catch(() => [])
    }
    if (targetStoreId.value) {
      targetCategories.value = await _ensureCategories(targetStoreId.value).catch(() => [])
    }
    dialogMode.value = 'create'
    dialogMapping.value = null
    submitError.value = null
    dialogOpen.value = true
  }

  function openEditDialog(mapping: MappingRow): void {
    dialogMode.value = 'edit'
    dialogMapping.value = mapping
    submitError.value = null
    dialogOpen.value = true
  }

  function closeDialog(): void {
    dialogOpen.value = false
    dialogMapping.value = null
    submitError.value = null
  }

  async function submitDialog(form: MappingFormModel): Promise<void> {
    submitError.value = null
    if (!refStoreId.value || !targetStoreId.value) return

    submitPending.value = true
    try {
      let updated: MappingRow[]
      if (dialogMode.value === 'create') {
        if (!form.reference_category_id || !form.target_category_id) {
          submitError.value = "Оберіть обидві категорії"
          return
        }
        updated = await createCategoryMapping({
          reference_category_id: Number(form.reference_category_id),
          target_category_id: Number(form.target_category_id),
          match_type: form.match_type.trim() || null,
          confidence: form.confidence !== '' ? parseFloat(form.confidence) : null,
        })
      } else {
        if (!dialogMapping.value) return
        updated = await updateCategoryMapping(
          dialogMapping.value.id,
          {
            match_type: form.match_type.trim() || null,
            confidence: form.confidence !== '' ? parseFloat(form.confidence) : null,
          },
          refStoreId.value,
          targetStoreId.value,
        )
      }
      mappings.value = updated
      closeDialog()
    } catch (err) {
      submitError.value = err instanceof Error ? err.message : String(err)
    } finally {
      submitPending.value = false
    }
  }

  async function deleteMappingById(mappingId: number): Promise<void> {
    if (deletingIds.value.has(mappingId)) return
    if (!refStoreId.value || !targetStoreId.value) return

    deletingIds.value = new Set([...deletingIds.value, mappingId])
    error.value = null
    try {
      const updated = await deleteCategoryMapping(
        mappingId,
        refStoreId.value,
        targetStoreId.value,
      )
      mappings.value = updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      const s = new Set(deletingIds.value)
      s.delete(mappingId)
      deletingIds.value = s
    }
  }

  async function triggerAutoLink(): Promise<void> {
    if (!refStoreId.value || !targetStoreId.value) return
    autoLinkPending.value = true
    autoLinkSummary.value = null
    error.value = null
    try {
      // Single round-trip: the enriched response contains both summary and
      // the updated mappings list, so no second fetchCategoryMappings() needed.
      const result = await autoLinkCategoryMappings(
        refStoreId.value,
        targetStoreId.value,
      )
      autoLinkSummary.value = result
      mappings.value = result.mappings
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      autoLinkPending.value = false
    }
  }

  function clearAutoLinkSummary(): void {
    autoLinkSummary.value = null
  }

  // ── Drawer actions (Commit 04) ────────────────────────────────────────────

  async function openCreateDrawer(): Promise<void> {
    if (refStoreId.value) {
      refCategories.value = await _ensureCategories(refStoreId.value).catch(() => [])
    }
    // Ensure target categories are ready so the drawer can show them immediately
    if (targetStoreId.value) {
      targetCategories.value = await _ensureCategories(targetStoreId.value).catch(() => [])
    }
    drawerMode.value = 'create'
    drawerMapping.value = null
    submitError.value = null
    drawerOpen.value = true
  }

  function openEditDrawer(mapping: MappingRow): void {
    drawerMode.value = 'edit'
    drawerMapping.value = mapping
    submitError.value = null
    drawerOpen.value = true
  }

  function closeDrawer(): void {
    drawerOpen.value = false
    drawerMapping.value = null
    submitError.value = null
  }

  async function submitDrawer(form: DrawerFormModel): Promise<void> {
    submitError.value = null
    submitPending.value = true
    try {
      let updated: MappingRow[]
      if (drawerMode.value === 'create') {
        if (!form.reference_category_id || !form.target_category_id) {
          submitError.value = 'Оберіть обидві категорії'
          return
        }
        updated = await createCategoryMapping({
          reference_category_id: Number(form.reference_category_id),
          target_category_id: Number(form.target_category_id),
          match_type: null,
          confidence: null,
        })
      } else {
        if (!drawerMapping.value || !refStoreId.value || !targetStoreId.value) return
        updated = await updateCategoryMapping(
          drawerMapping.value.id,
          { match_type: null, confidence: null },
          refStoreId.value,
          targetStoreId.value,
        )
      }
      mappings.value = updated
      closeDrawer()
    } catch (err) {
      submitError.value = err instanceof Error ? err.message : String(err)
    } finally {
      submitPending.value = false
    }
  }

  // Init: load stores list immediately
  fetchStores().then((s) => { stores.value = s }).catch(() => {})

  return {
    stores,
    refStoreId,
    targetStoreId,
    refCategories,
    targetCategories,
    mappings,
    loading,
    error,
    submitPending,
    submitError,
    deletingIds,
    autoLinkPending,
    autoLinkSummary,
    clearAutoLinkSummary,
    dialogOpen,
    dialogMode,
    dialogMapping,
    closeDialog,
    submitDialog,
    drawerOpen,
    drawerMode,
    drawerMapping,
    openCreateDrawer,
    openEditDrawer,
    closeDrawer,
    submitDrawer,
    setRefStore,
    setTargetStore,
    loadMappings,
    openCreateDialog,
    openEditDialog,
    deleteMappingById,
    triggerAutoLink,
  }
}

