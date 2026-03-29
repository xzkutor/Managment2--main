/**
 * mappings.test.ts — Unit tests for the mappings API adapter.
 */
import { describe, it, expect } from 'vitest'
import {
  adaptMapping,
  adaptMappingList,
  adaptAutoLinkSummary,
  adaptAutoLinkResult,
} from '@/api/adapters/mappings'

const rawMapping = {
  id: 1,
  reference_category_id: 10,
  target_category_id: 20,
  reference_category_name: 'Ковзани',
  target_category_name: 'Skates',
  reference_store_id: 1,
  target_store_id: 2,
  reference_store_name: 'prohockey',
  target_store_name: 'hockeyworld',
  match_type: 'exact',
  confidence: 1.0,
  updated_at: '2026-01-01T00:00:00',
}

// ---------------------------------------------------------------------------
// adaptMapping
// ---------------------------------------------------------------------------

describe('adaptMapping', () => {
  it('maps all fields correctly', () => {
    const result = adaptMapping(rawMapping)
    expect(result.id).toBe(1)
    expect(result.reference_category_id).toBe(10)
    expect(result.target_category_id).toBe(20)
    expect(result.reference_category_name).toBe('Ковзани')
    expect(result.target_category_name).toBe('Skates')
    expect(result.reference_store_id).toBe(1)
    expect(result.target_store_id).toBe(2)
    expect(result.match_type).toBe('exact')
    expect(result.confidence).toBe(1.0)
    expect(result.updated_at).toBe('2026-01-01T00:00:00')
  })

  it('coerces null-ish fields to null', () => {
    const result = adaptMapping({
      ...rawMapping,
      reference_category_name: null,
      target_category_name: null,
      match_type: null,
      confidence: null,
      updated_at: null,
    })
    expect(result.reference_category_name).toBeNull()
    expect(result.target_category_name).toBeNull()
    expect(result.match_type).toBeNull()
    expect(result.confidence).toBeNull()
    expect(result.updated_at).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// adaptMappingList
// ---------------------------------------------------------------------------

describe('adaptMappingList', () => {
  it('returns an array of MappingRow', () => {
    const result = adaptMappingList([rawMapping, rawMapping])
    expect(result).toHaveLength(2)
    expect(result[0].id).toBe(1)
  })

  it('tolerates an empty array', () => {
    expect(adaptMappingList([])).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// adaptAutoLinkSummary
// ---------------------------------------------------------------------------

describe('adaptAutoLinkSummary', () => {
  it('maps all summary fields', () => {
    const result = adaptAutoLinkSummary({ created: 3, skipped_existing: 1, skipped_no_norm: 0 })
    expect(result.created).toBe(3)
    expect(result.skipped_existing).toBe(1)
    expect(result.skipped_no_norm).toBe(0)
  })

  it('defaults missing fields to 0', () => {
    const result = adaptAutoLinkSummary({})
    expect(result.created).toBe(0)
    expect(result.skipped_existing).toBe(0)
    expect(result.skipped_no_norm).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// adaptAutoLinkResult — enriched response (Commit 3)
// ---------------------------------------------------------------------------

describe('adaptAutoLinkResult', () => {
  it('returns summary + mappings from enriched response', () => {
    const raw = {
      summary: { created: 2, skipped_existing: 1, skipped_no_norm: 0 },
      mappings: [rawMapping],
    }
    const result = adaptAutoLinkResult(raw)
    expect(result.summary.created).toBe(2)
    expect(result.mappings).toHaveLength(1)
    expect(result.mappings[0].id).toBe(1)
  })

  it('returns empty mappings when mappings key is absent (backward compat)', () => {
    const raw = {
      summary: { created: 0, skipped_existing: 0, skipped_no_norm: 0 },
    }
    const result = adaptAutoLinkResult(raw)
    expect(result.mappings).toEqual([])
  })

  it('defaults summary to zeros when summary key is absent', () => {
    const raw = { mappings: [rawMapping] }
    const result = adaptAutoLinkResult(raw)
    expect(result.summary.created).toBe(0)
    expect(result.mappings).toHaveLength(1)
  })
})

