/**
 * patchComparisonResult.ts — Pure helper for local ComparisonResult patching.
 *
 * Exported functions are deterministic and side-effect-free: they accept the
 * current ComparisonResult and the acted-on pair ids and return a new object.
 * They never mutate the input.
 *
 * Usage:
 *   import { applyDecisionPatch } from './patchComparisonResult'
 *   comparisonResult.value = applyDecisionPatch(comparisonResult.value, refId, tgtId)
 */
import type { ComparisonResult } from '../types'

/**
 * Remove the acted-on (refProductId, tgtProductId) pair from whichever section
 * of the result currently contains it:
 *
 * 1. `confirmed_matches` — removes the entry whose reference_product.id + target_product.id match.
 * 2. `candidate_groups`  — removes the matching candidate from the group; drops the whole group
 *    if it becomes empty after the removal.
 *
 * All other sections (`reference_only`, `target_only`, unaffected groups / matches)
 * are preserved exactly as-is. The `summary.candidate_groups` count is updated to
 * reflect the new `candidate_groups` length.
 *
 * @param prev         - current ComparisonResult (not mutated)
 * @param refProductId - reference_product.id of the acted-on pair
 * @param tgtProductId - target_product.id of the acted-on pair
 * @returns            a new ComparisonResult with the pair removed
 */
export function applyDecisionPatch(
  prev: ComparisonResult,
  refProductId: number,
  tgtProductId: number,
): ComparisonResult {
  // 1. Remove from confirmed_matches (auto-suggestions section)
  const newConfirmedMatches = prev.confirmed_matches.filter(
    (m) => !(m.reference_product?.id === refProductId && m.target_product?.id === tgtProductId),
  )

  // 2. Remove matching candidate from candidate_groups;
  //    drop the whole group if it becomes empty.
  const newCandidateGroups = prev.candidate_groups
    .map((group) => {
      if (group.reference_product?.id !== refProductId) return group
      return {
        ...group,
        candidates: group.candidates.filter(
          (c) => c.target_product?.id !== tgtProductId,
        ),
      }
    })
    .filter((group) => group.candidates.length > 0)

  return {
    ...prev,
    confirmed_matches: newConfirmedMatches,
    candidate_groups:  newCandidateGroups,
    summary: {
      ...prev.summary,
      candidate_groups: newCandidateGroups.length,
    },
  }
}

