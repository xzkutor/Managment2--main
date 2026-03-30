/**
 * useServiceCategories.ts — Categories tab state and action composable.
 *
 * Owns:
 *   - stores list + loading
 *   - admin store-sync action
 *   - per-pane state: selectedStoreId, categories, loading, status, sync actions
 *   - scrape status runs
 *
 * enableAdminSync is read from the normalized bootstrap via useBootstrapConfig.
 */
import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { useBootstrapConfig } from '@/composables/useBootstrapConfig'
import {
  fetchStores,
  syncAdminStores,
  fetchCategoriesForStore,
  syncStoreCategories,
  syncCategoryProducts,
  fetchScrapeStatus,
  type ProductSyncSummary,
} from '@/api/client'
import type { StoreSummary, CategorySummary } from '@/types/store'
import type { ScrapeRunSummary } from '@/types/history'
import type { StatusKind } from '@/types/common'

// ---------------------------------------------------------------------------
// Public pane types
// ---------------------------------------------------------------------------

export interface PaneState {
  storeId: Ref<number | null>
  categories: Ref<CategorySummary[]>
  loading: Ref<boolean>
  statusText: Ref<string>
  statusKind: Ref<StatusKind>
  syncLoading: Ref<boolean>
  syncProductsLoadingId: Ref<number | null>
}

export interface PaneActions {
  setStore: (id: number | null) => void
  loadCategories: () => Promise<void>
  triggerSync: () => Promise<void>
  triggerProductSync: (categoryId: number) => Promise<void>
}

export type PaneModel = PaneState & PaneActions

// ---------------------------------------------------------------------------
// Full composable return type
// ---------------------------------------------------------------------------

export interface ServiceCategoriesState {
  enableAdminSync: ComputedRef<boolean>
  stores: Ref<StoreSummary[]>
  storesLoading: Ref<boolean>
  storeSyncLoading: Ref<boolean>
  storeSyncStatus: Ref<{ text: string; kind: StatusKind } | null>
  triggerStoreSync: () => void
  /** Single-workspace pane state (formerly targetPane; refPane removed). */
  targetPane: PaneModel
  scrapeRuns: Ref<ScrapeRunSummary[]>
  scrapeRunsLoading: Ref<boolean>
  reloadScrapeStatus: () => void
}

// ---------------------------------------------------------------------------
// Main composable
// ---------------------------------------------------------------------------

export function useServiceCategories(): ServiceCategoriesState {
  // ── Admin config ──────────────────────────────────────────────
  const enableAdminSync = computed<boolean>(
    () => useBootstrapConfig().enableAdminSync,
  )

  // ── Stores ────────────────────────────────────────────────────
  const stores = ref<StoreSummary[]>([])
  const storesLoading = ref(false)
  const storeSyncLoading = ref(false)
  const storeSyncStatus = ref<{ text: string; kind: StatusKind } | null>(null)

  async function loadStores() {
    storesLoading.value = true
    try {
      stores.value = await fetchStores()
    } catch (err: unknown) {
      console.error('[categories] failed to load stores:', err)
    } finally {
      storesLoading.value = false
    }
  }

  function triggerStoreSync() {
    void (async () => {
      storeSyncLoading.value = true
      storeSyncStatus.value = { text: 'Синхронізація магазинів…', kind: 'warning' }
      try {
        stores.value = await syncAdminStores()
        storeSyncStatus.value = { text: 'Магазини синхронізовано', kind: 'success' }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err)
        storeSyncStatus.value = { text: `Помилка: ${msg}`, kind: 'error' }
      } finally {
        storeSyncLoading.value = false
      }
    })()
  }

  // ── Scrape status ─────────────────────────────────────────────
  const scrapeRuns = ref<ScrapeRunSummary[]>([])
  const scrapeRunsLoading = ref(false)

  async function loadScrapeStatus() {
    scrapeRunsLoading.value = true
    try {
      scrapeRuns.value = await fetchScrapeStatus()
    } catch {
      // non-critical widget — silently ignore errors
    } finally {
      scrapeRunsLoading.value = false
    }
  }

  // ── Pane factory ──────────────────────────────────────────────
  function makePaneModel(): PaneModel {
    const storeId = ref<number | null>(null)
    const categories = ref<CategorySummary[]>([])
    const loading = ref(false)
    const statusText = ref('Очікування')
    const statusKind = ref<StatusKind>('info')
    const syncLoading = ref(false)
    const syncProductsLoadingId = ref<number | null>(null)

    async function loadCategories() {
      if (!storeId.value) {
        categories.value = []
        statusText.value = 'Оберіть магазин'
        statusKind.value = 'info'
        return
      }
      loading.value = true
      statusText.value = 'Завантаження…'
      statusKind.value = 'warning'
      try {
        const result = await fetchCategoriesForStore(storeId.value)
        categories.value = result
        statusText.value = `Категорій: ${result.length}`
        statusKind.value = result.length > 0 ? 'success' : 'info'
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err)
        statusText.value = msg
        statusKind.value = 'error'
        categories.value = []
      } finally {
        loading.value = false
      }
    }

    function setStore(id: number | null) {
      storeId.value = id
      void loadCategories()
    }

    async function triggerSync() {
      if (!storeId.value) {
        statusText.value = 'Спочатку оберіть магазин'
        statusKind.value = 'warning'
        return
      }
      syncLoading.value = true
      statusText.value = 'Запуск синхронізації…'
      statusKind.value = 'warning'
      try {
        const result = await syncStoreCategories(storeId.value)
        categories.value = result
        statusText.value = `Синхронізовано: ${result.length} категорій`
        statusKind.value = 'success'
        void loadScrapeStatus()
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err)
        statusText.value = msg
        statusKind.value = 'error'
      } finally {
        syncLoading.value = false
      }
    }

    async function triggerProductSync(categoryId: number) {
      syncProductsLoadingId.value = categoryId
      statusText.value = 'Синхронізація товарів…'
      statusKind.value = 'warning'
      try {
        const summary: ProductSyncSummary = await syncCategoryProducts(categoryId)
        statusText.value = [
          `оброблено ${summary.products_processed ?? 0}`,
          `створено ${summary.products_created ?? 0}`,
          `оновлено ${summary.products_updated ?? 0}`,
          `змін ціни ${summary.price_changes_detected ?? 0}`,
        ].join(' · ')
        statusKind.value = 'success'
        void loadScrapeStatus()
        if (storeId.value) void loadCategories()
        setTimeout(() => {
          statusText.value = 'Очікування'
          statusKind.value = 'info'
        }, 4000)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err)
        statusText.value = `Помилка: ${msg}`
        statusKind.value = 'error'
      } finally {
        syncProductsLoadingId.value = null
      }
    }

    return {
      storeId,
      categories,
      loading,
      statusText,
      statusKind,
      syncLoading,
      syncProductsLoadingId,
      setStore,
      loadCategories,
      triggerSync,
      triggerProductSync,
    }
  }

  // ── Instantiate pane model ────────────────────────────────────
  // Single-workspace: only one pane (targetPane). refPane removed (Commit 5 fixup).
  const targetPane = makePaneModel()

  // ── Bootstrap ─────────────────────────────────────────────────
  void loadStores()
  void loadScrapeStatus()

  return {
    enableAdminSync,
    stores,
    storesLoading,
    storeSyncLoading,
    storeSyncStatus,
    triggerStoreSync,
    targetPane,
    scrapeRuns,
    scrapeRunsLoading,
    reloadScrapeStatus: () => void loadScrapeStatus(),
  }
}
