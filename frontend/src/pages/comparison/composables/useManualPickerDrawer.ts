/**
 * useManualPickerDrawer.ts — Page-level state for the shared manual picker drawer.
 *
 * Owns: open/close state, active reference product context, target category ids.
 * Single instance lives in ComparisonPage; child components emit open-picker events.
 */
import { ref } from 'vue'
import type { ComparisonProduct } from '../types'

export function useManualPickerDrawer() {
  const isOpen                 = ref(false)
  const drawerRefProduct       = ref<ComparisonProduct | null>(null)
  const drawerTargetCategoryIds = ref<number[]>([])

  function openDrawer(refProduct: ComparisonProduct, targetCategoryIds: number[]): void {
    drawerRefProduct.value        = refProduct
    drawerTargetCategoryIds.value = targetCategoryIds
    isOpen.value                  = true
  }

  function closeDrawer(): void {
    isOpen.value                  = false
    drawerRefProduct.value        = null
    drawerTargetCategoryIds.value = []
  }

  return {
    isOpen,
    drawerRefProduct,
    drawerTargetCategoryIds,
    openDrawer,
    closeDrawer,
  }
}

