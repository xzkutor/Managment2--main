/**
 * useManualPicker.ts — Manual picker state for one reference product.
 *
 * Manages:
 *   - search text
 *   - include_rejected toggle
 *   - debounced eligible-target-products search
 *   - products list / loading / error
 *
 * Usage: instantiate once per ManualPicker component instance.
 * getRefProductId is a getter function so callers can reactively switch products.
 */
import { ref } from 'vue'
import { searchEligibleTargetProducts } from '../api'
import type { EligibleProduct } from '../types'

export function useManualPicker(
  getRefProductId: () => number,
  getTargetCategoryIds: () => number[],
) {
  const search         = ref('')
  const includeRejected = ref(false)
  const products       = ref<EligibleProduct[]>([])
  const isSearching    = ref(false)
  const searchError    = ref<string | null>(null)

  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  function _triggerSearch() {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(async () => {
      const q = search.value.trim()
      if (q.length < 2) {
        products.value = []
        return
      }
      isSearching.value = true
      searchError.value = null
      try {
        products.value = await searchEligibleTargetProducts({
          referenceProductId: getRefProductId(),
          targetCategoryIds:  getTargetCategoryIds(),
          search:             q,
          includeRejected:    includeRejected.value,
        })
      } catch (err) {
        searchError.value = err instanceof Error ? err.message : String(err)
        products.value    = []
      } finally {
        isSearching.value = false
      }
    }, 300)
  }

  function onSearchInput(val: string): void {
    search.value = val
    _triggerSearch()
  }

  function setIncludeRejected(val: boolean): void {
    includeRejected.value = val
    if (search.value.trim().length >= 2) _triggerSearch()
  }

  function reset(): void {
    if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null }
    search.value         = ''
    products.value       = []
    includeRejected.value = false
    searchError.value    = null
    isSearching.value    = false
  }

  return {
    search,
    includeRejected,
    products,
    isSearching,
    searchError,
    onSearchInput,
    setIncludeRejected,
    reset,
  }
}
