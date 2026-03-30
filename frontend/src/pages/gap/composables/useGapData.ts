/**
 * useGapData.ts — Gap query state for POST /api/gap.
 *
 * Mutation UX policy:
 *   - loadGap() is non-destructive for subsequent loads: current result stays
 *     visible while the new request is in-flight (loading=true but result unchanged).
 *   - Only the very first load (hasLoaded===false) treats result as empty initially.
 */
import { ref, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { postGapQuery } from '@/api/gap'
import type { GapResult, GapRequestBody } from '@/types/gap'

export interface GapDataState {
  result: Ref<GapResult | null>
  loading: Ref<boolean>
  error: Ref<string | null>
  hasLoaded: Ref<boolean>
  lastBody: Ref<GapRequestBody | null>
  loadGap: (body: GapRequestBody) => Promise<void>
  /** Commit 1 — workspace state helpers */
  hasNeverLoaded: ComputedRef<boolean>
  hasResults: ComputedRef<boolean>
  isEmptyAfterLoad: ComputedRef<boolean>
  hasBlockingError: ComputedRef<boolean>
}

export function useGapData(): GapDataState {
  const result = ref<GapResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const hasLoaded = ref(false)
  const lastBody = ref<GapRequestBody | null>(null)

  // Commit 1 — explicit workspace state computed properties
  /** True when no successful or failed load has been triggered yet. */
  const hasNeverLoaded = computed(() => !hasLoaded.value && !loading.value && !error.value)
  /** True when the last load returned at least one group. */
  const hasResults = computed(() => hasLoaded.value && (result.value?.groups?.length ?? 0) > 0)
  /** True when loaded but result has zero groups (all filtered out or genuinely empty). */
  const isEmptyAfterLoad = computed(() => hasLoaded.value && (result.value?.groups?.length ?? 0) === 0)
  /** True when there is a blocking error on the last request. */
  const hasBlockingError = computed(() => !!error.value)

  async function loadGap(body: GapRequestBody): Promise<void> {
    loading.value = true
    error.value = null
    // Keep current result visible during reload — do NOT clear result or hasLoaded
    lastBody.value = body

    try {
      result.value = await postGapQuery(body)
      hasLoaded.value = true
    } catch (err) {
      error.value = 'Помилка запиту: ' + (err instanceof Error ? err.message : String(err))
    } finally {
      loading.value = false
    }
  }

  return { result, loading, error, hasLoaded, lastBody, loadGap, hasNeverLoaded, hasResults, isEmptyAfterLoad, hasBlockingError }
}
