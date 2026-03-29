/**
 * frontend/src/api/adapters/mappings.ts — Category mappings API adapter.
 *
 * Converts raw /api/category-mappings server payloads to stable frontend DTOs.
 */
import type { MappingRow, AutoLinkSummary, AutoLinkResult } from '@/types/mappings'

// ---------------------------------------------------------------------------
// Raw server shapes (as returned by serializers.py serialize_mapping)
// ---------------------------------------------------------------------------

interface RawMapping {
  id: number
  reference_category_id: number
  target_category_id: number
  reference_category_name: string | null
  target_category_name: string | null
  reference_store_id: number | null
  target_store_id: number | null
  reference_store_name: string | null
  target_store_name: string | null
  match_type: string | null
  confidence: number | null
  updated_at: string | null
}

interface RawAutoLinkSummary {
  created?: number
  skipped_existing?: number
  skipped_no_norm?: number
}

/** Enriched auto-link server response — summary + mappings list in one payload. */
interface RawAutoLinkResult {
  summary?: RawAutoLinkSummary
  mappings?: RawMapping[]
}

// ---------------------------------------------------------------------------
// Adapters
// ---------------------------------------------------------------------------

export function adaptMapping(raw: RawMapping): MappingRow {
  return {
    id: raw.id,
    reference_category_id: raw.reference_category_id,
    target_category_id: raw.target_category_id,
    reference_category_name: raw.reference_category_name ?? null,
    target_category_name: raw.target_category_name ?? null,
    reference_store_id: raw.reference_store_id ?? null,
    target_store_id: raw.target_store_id ?? null,
    match_type: raw.match_type ?? null,
    confidence: raw.confidence ?? null,
    updated_at: raw.updated_at ?? null,
  }
}

export function adaptMappingList(raw: RawMapping[]): MappingRow[] {
  return (raw ?? []).map(adaptMapping)
}

export function adaptAutoLinkSummary(raw: RawAutoLinkSummary): AutoLinkSummary {
  return {
    created: raw.created ?? 0,
    skipped_existing: raw.skipped_existing ?? 0,
    skipped_no_norm: raw.skipped_no_norm ?? 0,
  }
}

/**
 * Adapt the enriched auto-link response.
 * Tolerates missing `mappings` for backward compatibility with any older
 * server versions that return only the summary.
 */
export function adaptAutoLinkResult(raw: RawAutoLinkResult): AutoLinkResult {
  return {
    summary: adaptAutoLinkSummary(raw.summary ?? {}),
    mappings: adaptMappingList((raw.mappings ?? []) as RawMapping[]),
  }
}


// ---------------------------------------------------------------------------
// Raw server shapes (as returned by serializers.py serialize_mapping)
// ---------------------------------------------------------------------------

interface RawMapping {
  id: number
  reference_category_id: number
  target_category_id: number
  reference_category_name: string | null
  target_category_name: string | null
  reference_store_id: number | null
  target_store_id: number | null
  reference_store_name: string | null
  target_store_name: string | null
  match_type: string | null
  confidence: number | null
  updated_at: string | null
}

interface RawAutoLinkSummary {
  created?: number
  skipped_existing?: number
  skipped_no_norm?: number
}

/** Enriched auto-link server response — summary + mappings list in one payload. */
interface RawAutoLinkResult {
  summary?: RawAutoLinkSummary
  mappings?: RawMapping[]
}

