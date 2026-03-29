/**
 * useComparisonPage.ts — Page-level state for the main comparison page.
 *
 * Owns:
 *   - store loading + auto-selection of single reference store
 *   - reference category selection + dependent mapped-targets loading
 *   - target store filter changes
 *   - comparison execution (POST /api/comparison)
 *   - confirm / reject decisions with local state patching
 *
 * Mutation UX policy:
 *   - compare()       — foreground: clears visible result before fetch (manual button)
 *   - makeDecision()  — local patch via applyDecisionPatch(): removes only the
 *     acted-on pair from comparisonResult. No full re-compare is triggered.
 *     Pure patching logic lives in patchComparisonResult.ts.
 */
import { ref, computed } from 'vue'
import {
  fetchStores,
  fetchCategoriesForStore,
  fetchMappedTargets,
  runComparison,
  saveMatchDecision,
} from '../api'
import type { StoreSummary, CategorySummary } from '@/types/store'
import type { MappedTarget, ComparisonResult, MatchStatus } from '../types'
import { applyDecisionPatch } from './patchComparisonResult'

export function useComparisonPage() {
  // ── Stores ──────────────────────────────────────────────────────────────
  const allStores         = ref<StoreSummary[]>([])
  const isLoadingStores   = ref(false)
  const storesError       = ref<string | null>(null)

  const referenceStores = computed(() => allStores.value.filter((s) => s.is_reference))
  const targetStores    = computed(() => allStores.value.filter((s) => !s.is_reference))

  // ── Selections ──────────────────────────────────────────────────────────
  const referenceStoreId = ref<number | null>(null)
  const targetStoreId    = ref<number | null>(null)

  // ── Reference categories ────────────────────────────────────────────────
  const referenceCategories    = ref<CategorySummary[]>([])
  const isLoadingRefCategories = ref(false)
  const referenceCategoryId    = ref<number | null>(null)

  // ── Mapped target categories (checkboxes) ───────────────────────────────
  const mappedTargets           = ref<MappedTarget[]>([])
  const isLoadingMappedTargets  = ref(false)
  const selectedTargetCategoryIds = ref<Set<number>>(new Set())
  const noMappingsWarning       = ref(false)

  // ── Page status text ────────────────────────────────────────────────────
  const pageStatus = ref<string>('Завантажуємо магазини…')

  // ── Comparison state ────────────────────────────────────────────────────
  const isComparing      = ref(false)
  const comparisonResult = ref<ComparisonResult | null>(null)
  const comparisonError  = ref<string | null>(null)
  const hasCompared      = ref(false)

  // ── Decision in-flight tracking ─────────────────────────────────────────
  const decisionInProgressKey = ref<string | null>(null)  // `${refId}:${tgtId}`
  const decisionError         = ref<string | null>(null)

  // ── Derived ─────────────────────────────────────────────────────────────
  const canCompare = computed(
    () => referenceCategoryId.value !== null && selectedTargetCategoryIds.value.size > 0,
  )

  /** Auto-suggestions: confirmed_matches where is_confirmed === false */
  const autoSuggestions = computed(() =>
    (comparisonResult.value?.confirmed_matches ?? []).filter((m) => !m.is_confirmed),
  )

  // ── Workspace view-model (commit 1 — RFC-016) ────────────────────────────

  /** Currently selected reference category object (for display). */
  const currentReferenceCategory = computed(() =>
    referenceCategories.value.find((c) => c.id === referenceCategoryId.value) ?? null,
  )

  /** Currently selected target store object (for display). */
  const selectedTargetStore = computed(() =>
    targetStores.value.find((s) => s.id === targetStoreId.value) ?? null,
  )

  /** Counts for each review section — drives KPI cards and section visibility. */
  const reviewCounts = computed(() => ({
    autoSuggestions: autoSuggestions.value.length,
    candidateGroups: comparisonResult.value?.candidate_groups.length ?? 0,
    referenceOnly:   comparisonResult.value?.reference_only.length ?? 0,
    targetOnly:      comparisonResult.value?.target_only.length ?? 0,
  }))

  /** True when there is at least one item in any review section. */
  const hasReviewContent = computed(() =>
    hasCompared.value &&
    comparisonResult.value !== null &&
    (
      autoSuggestions.value.length > 0 ||
      (comparisonResult.value.candidate_groups.length > 0) ||
      (comparisonResult.value.reference_only.length > 0) ||
      (comparisonResult.value.target_only.length > 0)
    ),
  )

  /** High-level workspace state machine for template branching. */
  const comparisonWorkspaceState = computed<'idle' | 'comparing' | 'error' | 'review' | 'empty'>(() => {
    if (isComparing.value) return 'comparing'
    if (comparisonError.value) return 'error'
    if (hasReviewContent.value) return 'review'
    if (hasCompared.value) return 'empty'
    return 'idle'
  })

  // ── Actions ──────────────────────────────────────────────────────────────

  async function loadStores(): Promise<void> {
    isLoadingStores.value = true
    storesError.value = null
    try {
      allStores.value = await fetchStores()
      const refStores = allStores.value.filter((s) => s.is_reference)
      if (refStores.length === 1) {
        // Auto-select the single reference store
        await setReferenceStore(refStores[0].id)
      } else {
        pageStatus.value = 'Оберіть референсну категорію для порівняння.'
      }
    } catch (err) {
      const msg =
        'Помилка завантаження магазинів: ' +
        (err instanceof Error ? err.message : String(err))
      storesError.value = msg
      pageStatus.value = msg
    } finally {
      isLoadingStores.value = false
    }
  }

  async function setReferenceStore(id: number | null): Promise<void> {
    referenceStoreId.value    = id
    referenceCategoryId.value = null
    referenceCategories.value = []
    mappedTargets.value       = []
    selectedTargetCategoryIds.value = new Set()
    noMappingsWarning.value   = false
    comparisonResult.value    = null
    hasCompared.value         = false

    if (!id) {
      pageStatus.value = 'Оберіть референсну категорію для порівняння.'
      return
    }

    isLoadingRefCategories.value = true
    try {
      referenceCategories.value = await fetchCategoriesForStore(id)
      pageStatus.value = 'Оберіть референсну категорію для порівняння.'
    } catch {
      referenceCategories.value = []
    } finally {
      isLoadingRefCategories.value = false
    }
  }

  async function setTargetStore(id: number | null): Promise<void> {
    targetStoreId.value = id
    selectedTargetCategoryIds.value = new Set()
    if (referenceCategoryId.value) {
      await loadMappedTargets(referenceCategoryId.value)
    }
  }

  async function selectRefCategory(id: number): Promise<void> {
    referenceCategoryId.value       = id
    selectedTargetCategoryIds.value = new Set()
    mappedTargets.value             = []
    noMappingsWarning.value         = false
    await loadMappedTargets(id)
  }

  async function loadMappedTargets(refCatId: number): Promise<void> {
    isLoadingMappedTargets.value = true
    noMappingsWarning.value      = false
    try {
      const targets = await fetchMappedTargets(refCatId, targetStoreId.value)
      mappedTargets.value = targets
      if (!targets.length) {
        noMappingsWarning.value         = true
        selectedTargetCategoryIds.value = new Set()
      } else {
        selectedTargetCategoryIds.value = new Set(targets.map((t) => t.target_category_id))
      }
    } catch {
      mappedTargets.value             = []
      selectedTargetCategoryIds.value = new Set()
    } finally {
      isLoadingMappedTargets.value = false
    }
  }

  function toggleTargetCategory(id: number, checked: boolean): void {
    const next = new Set(selectedTargetCategoryIds.value)
    checked ? next.add(id) : next.delete(id)
    selectedTargetCategoryIds.value = next
  }

  // ── Section collapse state (RFC-016 v2, Commit 4) ──────────────────────
  const sectionExpanded = ref({
    autoSuggestions: false,
    candidateGroups: false,
    referenceOnly:   false,
  })

  function toggleSection(key: keyof typeof sectionExpanded.value): void {
    sectionExpanded.value = { ...sectionExpanded.value, [key]: !sectionExpanded.value[key] }
  }

  function _resetSectionExpanded(): void {
    sectionExpanded.value = { autoSuggestions: false, candidateGroups: false, referenceOnly: false }
  }

  // ── Internal ─────────────────────────────────────────────────────────────

  /** Shared API call — does NOT touch comparisonResult or hasCompared before fetch.
   *  Used for both foreground compare (after caller clears state) and background
   *  refresh after decisions (caller keeps current result visible). */
  async function _runComparison(): Promise<void> {
    if (!canCompare.value) return
    isComparing.value     = true
    comparisonError.value = null
    try {
      const body = {
        reference_category_id: referenceCategoryId.value!,
        target_category_ids:   Array.from(selectedTargetCategoryIds.value),
        ...(targetStoreId.value ? { target_store_id: targetStoreId.value } : {}),
      }
      comparisonResult.value = await runComparison(body)
      hasCompared.value      = true
    } catch (err) {
      comparisonError.value =
        'Помилка порівняння: ' + (err instanceof Error ? err.message : String(err))
    } finally {
      isComparing.value = false
    }
  }

  // ── Actions ──────────────────────────────────────────────────────────────

  /**
   * Foreground compare — triggered by the manual "Порівняти" button.
   * Clears visible result first so the UI resets cleanly before the request.
   */
  async function compare(): Promise<void> {
    comparisonResult.value = null
    hasCompared.value      = false
    _resetSectionExpanded()
    await _runComparison()
  }

  async function makeDecision(
    refProductId: number,
    tgtProductId: number,
    matchStatus: MatchStatus,
  ): Promise<void> {
    const key = `${refProductId}:${tgtProductId}`
    decisionInProgressKey.value = key
    decisionError.value         = null
    try {
      await saveMatchDecision({
        reference_product_id: refProductId,
        target_product_id:    tgtProductId,
        match_status:         matchStatus,
        ...(matchStatus === 'confirmed'
          ? { target_category_ids: Array.from(selectedTargetCategoryIds.value) }
          : {}),
      })
      // Local patch — delegate to pure helper; no full re-compare triggered.
      if (comparisonResult.value) {
        comparisonResult.value = applyDecisionPatch(comparisonResult.value, refProductId, tgtProductId)
      }
    } catch (err) {
      decisionError.value =
        'Помилка збереження рішення: ' + (err instanceof Error ? err.message : String(err))
    } finally {
      decisionInProgressKey.value = null
    }
  }

  return {
    // Read-only state
    allStores,
    referenceStores,
    targetStores,
    isLoadingStores,
    storesError,
    referenceStoreId,
    targetStoreId,
    referenceCategories,
    isLoadingRefCategories,
    referenceCategoryId,
    mappedTargets,
    isLoadingMappedTargets,
    selectedTargetCategoryIds,
    noMappingsWarning,
    pageStatus,
    isComparing,
    comparisonResult,
    comparisonError,
    hasCompared,
    decisionInProgressKey,
    decisionError,
    // Derived
    canCompare,
    autoSuggestions,
    currentReferenceCategory,
    selectedTargetStore,
    reviewCounts,
    hasReviewContent,
    comparisonWorkspaceState,
    // Actions
    loadStores,
    setReferenceStore,
    setTargetStore,
    selectRefCategory,
    toggleTargetCategory,
    compare,
    makeDecision,
    sectionExpanded,
    toggleSection,
  }
}

