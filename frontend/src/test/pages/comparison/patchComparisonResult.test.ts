/**
 * patchComparisonResult.test.ts — Unit tests for the pure comparison-patch helper.
 *
 * These tests are completely isolated from Vue rendering and composable setup.
 * They verify the deterministic behaviour of applyDecisionPatch() directly.
 */
import { describe, it, expect } from 'vitest'
import { applyDecisionPatch } from '@/pages/comparison/composables/patchComparisonResult'
import type { ComparisonResult } from '@/pages/comparison/types'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeProduct(id: number, name = `Product ${id}`) {
  return { id, name, price: '100.00', currency: 'UAH', product_url: null }
}

function makeResult(overrides: Partial<ComparisonResult> = {}): ComparisonResult {
  return {
    confirmed_matches: [
      {
        is_confirmed: false,
        reference_product: makeProduct(100),
        target_product:    makeProduct(200),
        target_category:   { name: 'Cat A', store_name: 'shop' },
        score_percent:     90,
        score_details:     null,
      },
      {
        is_confirmed: true,
        reference_product: makeProduct(101),
        target_product:    makeProduct(201),
        target_category:   { name: 'Cat B', store_name: 'shop' },
        score_percent:     95,
        score_details:     null,
      },
    ],
    candidate_groups: [
      {
        reference_product: makeProduct(102),
        candidates: [
          { target_product: makeProduct(202), target_category: null, score_percent: 70, score_details: null, can_accept: true, disabled_reason: null },
          { target_product: makeProduct(203), target_category: null, score_percent: 60, score_details: null, can_accept: true, disabled_reason: null },
        ],
      },
      {
        reference_product: makeProduct(103),
        candidates: [
          { target_product: makeProduct(204), target_category: null, score_percent: 65, score_details: null, can_accept: true, disabled_reason: null },
        ],
      },
    ],
    reference_only: [{ reference_product: makeProduct(104) }],
    target_only:    [{ target_product: makeProduct(205), target_category: null }],
    summary:        { candidate_groups: 2, reference_only: 1, target_only: 1 },
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// confirmed_matches patching
// ---------------------------------------------------------------------------

describe('applyDecisionPatch — confirmed_matches', () => {
  it('removes the matched pair from confirmed_matches', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 100, 200)
    expect(patched.confirmed_matches).toHaveLength(1)
    expect(patched.confirmed_matches[0].reference_product?.id).toBe(101)
  })

  it('keeps unaffected confirmed_matches entries intact', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 100, 200)
    expect(patched.confirmed_matches[0].target_product?.id).toBe(201)
  })

  it('is a no-op on confirmed_matches when ids do not match any entry', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 999, 888)
    expect(patched.confirmed_matches).toHaveLength(result.confirmed_matches.length)
  })

  it('results in empty confirmed_matches when the only entry is removed', () => {
    const result = makeResult({
      confirmed_matches: [{
        is_confirmed: false,
        reference_product: makeProduct(100),
        target_product:    makeProduct(200),
        target_category:   null,
        score_percent:     80,
        score_details:     null,
      }],
    })
    const patched = applyDecisionPatch(result, 100, 200)
    expect(patched.confirmed_matches).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// candidate_groups patching
// ---------------------------------------------------------------------------

describe('applyDecisionPatch — candidate_groups', () => {
  it('removes the matching candidate from a multi-candidate group', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 102, 202)
    const group = patched.candidate_groups.find(g => g.reference_product?.id === 102)
    expect(group).toBeDefined()
    expect(group!.candidates).toHaveLength(1)
    expect(group!.candidates[0].target_product?.id).toBe(203)
  })

  it('drops the whole group when its only candidate is removed', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 103, 204)
    expect(patched.candidate_groups.find(g => g.reference_product?.id === 103)).toBeUndefined()
  })

  it('updates summary.candidate_groups to reflect removed groups', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 103, 204)
    expect(patched.summary.candidate_groups).toBe(1)
  })

  it('keeps unaffected groups completely intact', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 103, 204)
    const other = patched.candidate_groups.find(g => g.reference_product?.id === 102)
    expect(other).toBeDefined()
    expect(other!.candidates).toHaveLength(2)
  })

  it('is a no-op on candidate_groups when ids do not match any group', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 999, 888)
    expect(patched.candidate_groups).toHaveLength(result.candidate_groups.length)
  })
})

// ---------------------------------------------------------------------------
// reference_only patching (RFC-016: manual match via drawer removes from list)
// ---------------------------------------------------------------------------

describe('applyDecisionPatch — reference_only', () => {
  it('removes the reference product from reference_only when matched', () => {
    const result = makeResult()
    // refProductId=104 is in reference_only; tgtProductId can be anything (not used for filtering)
    const patched = applyDecisionPatch(result, 104, 999)
    expect(patched.reference_only).toHaveLength(0)
  })

  it('updates summary.reference_only after removal', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 104, 999)
    expect(patched.summary.reference_only).toBe(0)
  })

  it('leaves reference_only unchanged when refProductId has no matching entry', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 100, 200) // refId 100 is in confirmed_matches, not reference_only
    expect(patched.reference_only).toHaveLength(result.reference_only.length)
    expect(patched.summary.reference_only).toBe(result.summary.reference_only)
  })

  it('keeps multiple reference_only items when only one is removed', () => {
    const result = makeResult({
      reference_only: [
        { reference_product: makeProduct(104) },
        { reference_product: makeProduct(105) },
      ],
      summary: { candidate_groups: 2, reference_only: 2, target_only: 1 },
    })
    const patched = applyDecisionPatch(result, 104, 999)
    expect(patched.reference_only).toHaveLength(1)
    expect(patched.reference_only[0].reference_product?.id).toBe(105)
    expect(patched.summary.reference_only).toBe(1)
  })
})

// ---------------------------------------------------------------------------
// Sections not affected by any decision
// ---------------------------------------------------------------------------

describe('applyDecisionPatch — untouched sections', () => {
  it('never mutates target_only', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 100, 200)
    expect(patched.target_only).toEqual(result.target_only)
  })

  it('preserves summary.target_only in all cases', () => {
    const result = makeResult()
    const patched = applyDecisionPatch(result, 103, 204)
    expect(patched.summary.target_only).toBe(result.summary.target_only)
  })

  it('does not mutate the input object', () => {
    const result = makeResult()
    const before = JSON.stringify(result)
    applyDecisionPatch(result, 100, 200)
    expect(JSON.stringify(result)).toBe(before)
  })
})

