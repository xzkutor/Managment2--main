/**
 * frontend/src/types/mappings.ts — Category mapping frontend DTO types.
 *
 * These reflect shapes returned by:
 *   GET    /api/category-mappings              → { mappings: MappingRow[] }
 *   POST   /api/category-mappings              → { mapping, mappings: MappingRow[] }
 *   PUT    /api/category-mappings/:id          → { mapping, mappings: MappingRow[] }
 *   DELETE /api/category-mappings/:id          → { mappings: MappingRow[] }
 *   POST   /api/category-mappings/auto-link    → AutoLinkResult
 */

// ---------------------------------------------------------------------------
// Mapping row
// ---------------------------------------------------------------------------

export interface MappingRow {
  id: number
  reference_category_id: number
  target_category_id: number
  reference_category_name: string | null
  target_category_name: string | null
  reference_store_id: number | null
  target_store_id: number | null
  match_type: string | null
  /** Fractional 0–1; display as percentage */
  confidence: number | null
  updated_at: string | null
}

// ---------------------------------------------------------------------------
// Auto-link result (enriched single-round-trip response)
// ---------------------------------------------------------------------------

export interface AutoLinkSummary {
  created: number
  skipped_existing: number
  skipped_no_norm: number
}

export interface AutoLinkResult {
  summary: AutoLinkSummary
  mappings: MappingRow[]
}

// ---------------------------------------------------------------------------
// Form models
// ---------------------------------------------------------------------------

/** Legacy full form model (kept for composable backward compat with submitDialog). */
export interface MappingFormModel {
  reference_category_id: string
  target_category_id: string
  match_type: string
  confidence: string
}

/**
 * Simplified drawer form model (Commit 05).
 * Excludes match_type and confidence — those are backend-managed.
 * target_store_id is used client-side only to load target categories.
 */
export interface DrawerFormModel {
  reference_category_id: string
  /** Client-side only: used to populate target category select. */
  target_store_id: string
  target_category_id: string
}
