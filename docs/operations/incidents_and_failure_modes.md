# Incidents and Failure Modes

## Purpose

This document lists likely operational failure modes for the project and gives a structured way to reason about detection, impact, mitigation, and follow-up actions.

It is not a pager-duty runbook. It is a system-oriented incident model and failure catalog.

## Failure Categories

### 1. External source failure
Examples:
- target store site unavailable;
- anti-bot or rate-limit responses;
- HTML structure changed;
- category pagination no longer works;
- product cards missing expected fields.

Impact:
- sync may fail partially or fully;
- stale catalog data;
- comparison/gap pages reflect outdated DB state.

Detection:
- failed scrape runs;
- sudden drop in parsed product counts;
- adapter contract tests failing;
- manual operator observation on `/service` history.

Mitigation:
- inspect latest run records;
- reproduce with adapter-specific checks;
- update adapter parser/selectors;
- if needed, temporarily stop affected sync path rather than persisting bad data.

Follow-up:
- add regression test for changed page structure;
- document source-specific quirk in adapter docs or comments.

### 2. Mapping drift / mapping quality regression
Examples:
- candidate heuristic starts overmatching;
- confirmed mappings become outdated after source catalog rename;
- category mapping points to incorrect semantic bucket.

Impact:
- incorrect comparison pairing;
- false missing/matched states;
- noisy gap backlog.

Detection:
- operator review complaints;
- tests around matching start failing;
- suspicious spike in ambiguous or mismatched outputs.

Mitigation:
- review confirmed mappings in service UI;
- correct or remove bad persisted mappings;
- tune normalization/matching heuristics;
- avoid bulk auto-confirming weak candidates.

Follow-up:
- capture problematic examples in tests;
- update comparison_and_matching docs if rules changed intentionally.

### 3. Persistence / migration failure
Examples:
- migration fails on deployment;
- schema mismatch between app code and DB;
- uniqueness assumptions violated;
- DB write partially succeeds due to transaction boundary issue.

Impact:
- application startup failure;
- broken sync or mapping workflows;
- inconsistent persisted truth.

Detection:
- migration command errors;
- repository tests failing;
- runtime exceptions on write paths.

Mitigation:
- stop further writes;
- inspect schema version and failing migration;
- restore transactional integrity;
- reconcile invalid rows before rerunning.

Follow-up:
- add migration verification notes;
- add test coverage for invariant-sensitive writes.

### 4. API contract drift
Examples:
- UI expects a response field no longer returned;
- endpoint envelope changes without doc/test updates;
- admin endpoint semantics change silently.

Impact:
- broken UI interactions;
- hidden regressions in automation/manual workflows.

Detection:
- contract tests fail;
- UI runtime errors;
- manual service page breakage.

Mitigation:
- restore previous shape or update all consumers and docs atomically;
- separate stable from internal endpoints more clearly.

Follow-up:
- expand API tests;
- finalize OpenAPI/spec outline for supported endpoints.

### 5. Gap workflow integrity failure
Examples:
- implicit `new` logic broken;
- explicit statuses written for wrong key/context;
- done items reappear unexpectedly because identity derivation changed.

Impact:
- operator loses trust in `/gap` workflow;
- duplicate work and review confusion.

Detection:
- inconsistent gap lists after status updates;
- unexpected growth of explicit status records;
- test failures in gap-specific cases.

Mitigation:
- verify identity key derivation for gap items;
- inspect explicit status table rows;
- restore rule that `new` is implicit.

Follow-up:
- add cross-case tests for reopen/recompute behavior;
- document identity composition more precisely if currently implicit in code.

### 6. Test coverage blind spot
Examples:
- adapter edge case not captured;
- docs updated but tests not updated;
- new store integration added without contract tests.

Impact:
- silent regressions;
- increased operator/manual validation load.

Detection:
- production behavior diverges from expectations despite green pipeline;
- issue repeats in neighboring adapters/features.

Mitigation:
- add failing regression test first;
- classify missing test layer: unit, repository, API, adapter, integration.

Follow-up:
- update testing strategy and contribution guidance.

## Severity Heuristics

### High
- persisted truth corrupted;
- comparison or gap results broadly misleading;
- migration/startup blocked;
- core supported UI path unusable.

### Medium
- one adapter/store degraded;
- admin flow partially impaired;
- gap workflow noisy but recoverable.

### Low
- legacy/debug path broken;
- cosmetic UI issue with intact domain behavior;
- documentation-only inconsistency.

## Incident Response Principles

1. Preserve persisted truth integrity over feature continuity.
2. Prefer stale-but-correct data over fresh-but-corrupted data.
3. Treat unsupported debug output as non-authoritative.
4. Fix docs and tests together when business behavior changes.
5. Add regression tests for every real incident class that reveals a missing invariant.

## Post-Incident Questions

- Was the failure in adapter, service, persistence, or contract layer?
- Did a documented invariant exist and was it violated, or was the invariant undocumented?
- Was the behavior covered by tests at the right layer?
- Did root README/docs mislead maintainers about expected behavior?
- Can the same failure recur in another store/adapter/route family?
