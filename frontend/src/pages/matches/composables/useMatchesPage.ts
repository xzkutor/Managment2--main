/**
 * useMatchesPage.ts — State and action composable for the /matches page.
 *
 * Owns:
 *   - stores list + split into reference/target
 *   - category lists per store side
 *   - filter state (referenceStoreId, targetStoreId, …)
 *   - mappings rows / total
 *   - loading / error / info states
 *   - delete action (with window.confirm guard)
 *
 * Mutation UX policy:
 *   - loadMappings() is non-destructive: existing rows stay visible while
 *     loading=true so the table does not disappear on filter/refresh.
 *   - deleteRow() removes the row locally after success — does NOT call
 *     loadMappings() to avoid a full table flash.
 *
 * Called from MatchesPage.vue — no direct DOM access here.
 */
import { ref, computed, reactive } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { fetchStores, fetchCategoriesForStore } from '@/api/client'
import { listProductMappings, deleteProductMapping } from '@/api/matches'
import type { StoreSummary, CategorySummary } from '@/types/store'
import type { ProductMappingRow, MatchesFilters } from '@/types/matches'

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

export interface MatchesPageState {
  // Stores
  stores: Ref<StoreSummary[]>
  referenceStores: ComputedRef<StoreSummary[]>
  targetStores: ComputedRef<StoreSummary[]>

  // Per-side categories
  referenceCategories: Ref<CategorySummary[]>
  targetCategories: Ref<CategorySummary[]>

  // Filters (reactive object — mutated directly by the composable actions)
  filters: MatchesFilters

  // Result state
  rows: Ref<ProductMappingRow[]>
  total: Ref<number>
  hasLoaded: Ref<boolean>

  // Async state flags
  isBootstrapping: Ref<boolean>
  isLoadingRows: Ref<boolean>
  isDeletingId: Ref<number | null>

  // Messages
  errorMessage: Ref<string | null>
  infoMessage: Ref<string | null>

  // Derived / computed state (Commit 1 — workspace redesign)
  /** true when rows.length > 0 */
  hasRows: ComputedRef<boolean>
  /** true when any loading/error/info banner should be visible */
  hasStatusBlock: ComputedRef<boolean>
  /** number of non-default filter values currently applied */
  activeFiltersCount: ComputedRef<number>
  /** KPI: total matches count (mirrors total) */
  kpiTotal: ComputedRef<number>
  /** KPI: confirmed rows in current page */
  kpiConfirmed: ComputedRef<number>
  /** KPI: rejected rows in current page */
  kpiRejected: ComputedRef<number>

  // Actions
  setReferenceStore: (id: number | null) => Promise<void>
  setTargetStore: (id: number | null) => Promise<void>
  loadMappings: () => Promise<void>
  deleteRow: (mappingId: number) => Promise<void>
  clearMessages: () => void
}

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

export function useMatchesPage(): MatchesPageState {
  // ── Stores ────────────────────────────────────────────────────
  const stores = ref<StoreSummary[]>([])
  const referenceStores = computed(() => stores.value.filter((s) => s.is_reference))
  const targetStores = computed(() => stores.value.filter((s) => !s.is_reference))

  const referenceCategories = ref<CategorySummary[]>([])
  const targetCategories = ref<CategorySummary[]>([])

  // ── Filters ───────────────────────────────────────────────────
  const filters = reactive<MatchesFilters>({
    referenceStoreId: null,
    targetStoreId: null,
    referenceCategoryId: null,
    targetCategoryId: null,
    status: 'confirmed',
    search: '',
  })

  // ── Result state ──────────────────────────────────────────────
  const rows = ref<ProductMappingRow[]>([])
  const total = ref(0)
  const hasLoaded = ref(false)

  // ── Async flags ───────────────────────────────────────────────
  const isBootstrapping = ref(false)
  const isLoadingRows = ref(false)
  const isDeletingId = ref<number | null>(null)

  // ── Messages ──────────────────────────────────────────────────
  const errorMessage = ref<string | null>(null)
  const infoMessage = ref<string | null>(null)

  // ── Internal helpers ──────────────────────────────────────────

  function _errMsg(err: unknown): string {
    return err instanceof Error ? err.message : String(err)
  }

  // ── Store loading (bootstrap) ─────────────────────────────────

  async function _loadStores(): Promise<void> {
    isBootstrapping.value = true
    try {
      stores.value = await fetchStores()
    } catch (err) {
      errorMessage.value = 'Помилка завантаження магазинів: ' + _errMsg(err)
    } finally {
      isBootstrapping.value = false
    }
  }

  // ── Store selection → category loading ───────────────────────

  async function setReferenceStore(id: number | null): Promise<void> {
    filters.referenceStoreId = id
    filters.referenceCategoryId = null
    referenceCategories.value = []
    if (id) {
      try {
        referenceCategories.value = await fetchCategoriesForStore(id)
      } catch {
        // silently ignore — category select stays empty
      }
    }
  }

  async function setTargetStore(id: number | null): Promise<void> {
    filters.targetStoreId = id
    filters.targetCategoryId = null
    targetCategories.value = []
    if (id) {
      try {
        targetCategories.value = await fetchCategoriesForStore(id)
      } catch {
        // silently ignore
      }
    }
  }

  // ── Load mappings ─────────────────────────────────────────────

  async function loadMappings(): Promise<void> {
    errorMessage.value = null
    infoMessage.value = null
    isLoadingRows.value = true
    // Do NOT clear rows/total/hasLoaded — keep current data visible during fetch

    try {
      const result = await listProductMappings(filters)
      rows.value = result.rows
      total.value = result.total
      hasLoaded.value = true
      if (!result.rows.length) {
        infoMessage.value = 'Збігів не знайдено для обраних фільтрів.'
      }
    } catch (err) {
      errorMessage.value = 'Помилка завантаження: ' + _errMsg(err)
    } finally {
      isLoadingRows.value = false
    }
  }

  // ── Delete row ────────────────────────────────────────────────

  async function deleteRow(mappingId: number): Promise<void> {
    if (!window.confirm(`Видалити маппінг #${mappingId}? Цю дію не можна скасувати.`)) return

    isDeletingId.value = mappingId
    errorMessage.value = null

    try {
      await deleteProductMapping(mappingId)
      // Local removal — do NOT reload the full list
      rows.value = rows.value.filter((r) => r.id !== mappingId)
      total.value = Math.max(0, total.value - 1)
      if (rows.value.length === 0) {
        infoMessage.value = 'Збігів не знайдено для обраних фільтрів.'
      }
    } catch (err) {
      errorMessage.value = 'Помилка видалення: ' + _errMsg(err)
    } finally {
      isDeletingId.value = null
    }
  }

  // ── Bootstrap ─────────────────────────────────────────────────
  void _loadStores()

  // ── Derived computed state (Commit 1 — workspace redesign) ───

  const hasRows = computed(() => rows.value.length > 0)

  const hasStatusBlock = computed(() =>
    isBootstrapping.value || isLoadingRows.value || !!errorMessage.value || !!infoMessage.value,
  )

  const activeFiltersCount = computed(() => {
    let n = 0
    if (filters.referenceStoreId !== null) n++
    if (filters.targetStoreId !== null) n++
    if (filters.referenceCategoryId !== null) n++
    if (filters.targetCategoryId !== null) n++
    if (filters.status !== '') n++
    if (filters.search !== '') n++
    return n
  })

  const kpiTotal = computed(() => total.value)
  const kpiConfirmed = computed(() => rows.value.filter((r) => r.match_status === 'confirmed').length)
  const kpiRejected = computed(() => rows.value.filter((r) => r.match_status === 'rejected').length)

  function clearMessages(): void {
    errorMessage.value = null
    infoMessage.value = null
  }

  return {
    stores,
    referenceStores,
    targetStores,
    referenceCategories,
    targetCategories,
    filters,
    rows,
    total,
    hasLoaded,
    isBootstrapping,
    isLoadingRows,
    isDeletingId,
    errorMessage,
    infoMessage,
    hasRows,
    hasStatusBlock,
    activeFiltersCount,
    kpiTotal,
    kpiConfirmed,
    kpiRejected,
    setReferenceStore,
    setTargetStore,
    loadMappings,
    deleteRow,
    clearMessages,
  }
}

