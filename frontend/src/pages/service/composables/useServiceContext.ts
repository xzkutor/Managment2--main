/**
 * useServiceContext.ts — lightweight service-scoped shared state.
 *
 * Provides a controlled way to share the "current target store" selection
 * across /service sub-sections without using window/global mutable state.
 *
 * Pattern: module-level Vue ref — safe, reactive, no Pinia overhead.
 *
 * Usage:
 *   // In Categories (writer):
 *   const ctx = useServiceContext()
 *   ctx.setTargetStore(id)
 *
 *   // In Mappings (reader):
 *   const ctx = useServiceContext()
 *   const defaultTargetId = ctx.currentTargetStoreId.value
 */
import { ref } from 'vue'
import type { Ref } from 'vue'

// Module-level reactive ref — shared across all components that call
// useServiceContext() within the same module instance (i.e., the SPA).
const _currentTargetStoreId = ref<number | null>(null)

export interface ServiceContext {
  /** Read-only view of the current target store id set by Categories. */
  currentTargetStoreId: Ref<number | null>
  /** Set when the operator selects a target store in any /service section. */
  setTargetStore: (id: number | null) => void
}

export function useServiceContext(): ServiceContext {
  return {
    currentTargetStoreId: _currentTargetStoreId,
    setTargetStore(id: number | null) {
      _currentTargetStoreId.value = id
    },
  }
}

