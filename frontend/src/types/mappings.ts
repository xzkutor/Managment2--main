/**
 * frontend/src/types/mappings.ts — Category mapping frontend DTO types.
 *
 * These reflect shapes returned by:
 *   GET    /api/category-mappings              → { mappings: MappingRow[] }
 *   POST   /api/category-mappings              → { mapping, mappings: MappingRow[] }
 *   PUT    /api/category-mappings/:id          → { mapping, mappings: MappingRow[] }
 *   DELETE /api/category-mappings/:id          → { mappings: MappingRow[] }
 *   POST   /api/category-mappings/auto-link    → AutoLinkResult
 *     (enriched response: summary + updated mappings list in one round-trip)
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

/**
 * Full response from POST /api/category-mappings/auto-link.
 *
 * Contains both the action summary and the up-to-date mapping list for the
 * (reference_store_id, target_store_id) pair, so the frontend can update its
 * state without an extra fetchCategoryMappings() call.
 */
export interface AutoLinkResult {
  summary: AutoLinkSummary
  mappings: MappingRow[]
}

// ---------------------------------------------------------------------------
// Form model (string bindings for <input> / <select> v-model)
// ---------------------------------------------------------------------------

export interface MappingFormModel {
  /** string for <select> v-model — empty string = not selected */
  reference_category_id: string
  /** string for <select> v-model — empty string = not selected */
  target_category_id: string
  match_type: string
  /** string for <input type="number"> v-model — empty string = null */
  confidence: string
}


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
// Auto-link result
// ---------------------------------------------------------------------------

export interface AutoLinkSummary {
  created: number
  skipped_existing: number
  skipped_no_norm: number
}

// ---------------------------------------------------------------------------
// Form model (string bindings for <input> / <select> v-model)
// ---------------------------------------------------------------------------

export interface MappingFormModel {
  /** string for <select> v-model — empty string = not selected */
  reference_category_id: string
  /** string for <select> v-model — empty string = not selected */
  target_category_id: string
  match_type: string
  /** string for <input type="number"> v-model — empty string = null */
  confidence: string
}

