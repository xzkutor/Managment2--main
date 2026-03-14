# RFC-012 — ScrapeRun Semantics and Retry Metadata Cleanup

**Status:** Proposed  
**Date:** 2026-03-14  
**Depends on:** ADR — ScrapeRun Semantics and Retry Metadata Clarification

## 1. Summary

This RFC defines the implementation path for clarifying and normalizing `ScrapeRun` semantics in the repository, with a specific focus on:

- canonical success status semantics
- compatibility handling for legacy `finished`
- explicit separation of retry processing vs retry exhaustion
- canonical retry linkage
- attempt and `max_retries` arithmetic
- lightweight distinction between legacy runs and scheduler-owned runs

The goal is to reduce semantic drift without introducing a large API break or a large table split.

---

## 2. Motivation

`ScrapeRun` now serves two overlapping concerns:

1. legacy/manual scrape history
2. scheduler-owned queue/execution history

This is currently acceptable, but several fields and behaviors are semantically overloaded:

- `run_type` now effectively represents runner identity, while `trigger_type` represents initiation cause
- `finished` still exists as a compatibility value even though `success` is the canonical success status
- `retry_exhausted` currently carries more than one meaning
- retry parent linkage can appear both in `retry_of_run_id` and in `metadata_json`
- attempt arithmetic is not yet formalized strongly enough for future-safe maintenance

Without clarification and cleanup, the model will become harder to reason about in:
- scheduler code
- worker code
- serializers/history/status surfaces
- UI filters
- operator workflows

---

## 3. Goals

This RFC aims to:

1. make `success` the canonical completed-success status;
2. retain `finished` only as a compatibility input/filter concept;
3. introduce explicit `retry_processed` semantics in this wave;
4. preserve `retry_exhausted` for literal retry-budget exhaustion semantics;
5. formalize `retry_of_run_id` as the canonical retry linkage;
6. formalize `attempt=1` as the initial attempt;
7. define `max_retries` as the number of additional retries beyond the initial attempt;
8. keep API/UI churn minimal and compatibility-aware.

---

## 4. Non-Goals

This RFC does **not**:

- rename `run_type` to `runner_type` in this wave;
- split `ScrapeRun` into separate legacy and scheduler tables;
- perform a broad `store_id`-centric cleanup;
- redesign scheduler ownership of retries;
- redesign repository claim semantics;
- perform a major API redesign for history or scheduler UI.

---

## 5. Canonical Semantics

## 5.1 Status semantics

### Canonical statuses
The canonical run status set remains:

- `queued`
- `running`
- `success`
- `partial`
- `failed`
- `cancelled`
- `skipped`

### Legacy compatibility
`finished` remains supported only as:
- a compatibility request/filter value
- a compatibility normalization input where older code/tests still reference it

Canonical output and canonical stored-success semantics should be `success`.

---

## 5.2 `run_type` vs `trigger_type`

### `trigger_type`
Represents initiation cause:
- scheduled
- manual
- retry

### `run_type`
Remains the legacy/public field representing runner identity.

This RFC explicitly keeps `run_type` unchanged in this wave and clarifies semantics instead of introducing a `runner_type` alias.

---

## 5.3 Retry linkage

`retry_of_run_id` is the canonical retry parent linkage.

`metadata_json` may temporarily still contain retry context for compatibility/debugging, but it is **not** the canonical source of retry lineage.

---

## 5.4 Retry state semantics

This RFC distinguishes three concepts:

1. **retryable**
   - whether the failed run is eligible in principle for retry scheduling

2. **retry_processed**
   - whether scheduler retry handling has already evaluated/handled this source run such that it must not produce another retry child

3. **retry_exhausted**
   - whether the configured retry budget is exhausted for that run lineage/policy context

The current overloaded use of `retry_exhausted` to mean both “already handled” and “budget exhausted” is explicitly deprecated by this RFC.

---

## 5.5 Attempt semantics

The attempt model is:

- initial run = `attempt=1`
- first retry = `attempt=2`
- second retry = `attempt=3`

`max_retries` counts **additional retries beyond the initial attempt**.

Examples:

- `max_retries=0` → only attempt 1 is allowed
- `max_retries=1` → attempts 1 and 2 are allowed
- `max_retries=2` → attempts 1, 2, and 3 are allowed

Implementation logic must align with this arithmetic.

---

## 5.6 Legacy runs vs scheduler-owned runs

Use a lightweight distinction:

- **scheduler-owned run**: `job_id IS NOT NULL`
- **legacy/manual run**: `job_id IS NULL`

This distinction may be encoded via helper predicates or repository/serializer helpers, but does not require a separate table.

`store_id` remains contextual/compatibility-oriented and is not the primary identity for scheduler-owned runs.

---

## 6. Data Model Changes

## 6.1 Add `retry_processed`
This wave introduces an explicit `retry_processed` field to `ScrapeRun`.

Purpose:
- mark that scheduler retry handling has already processed the source run
- prevent multiple retry-child creations from the same source run
- stop overloading `retry_exhausted`

## 6.2 Retain `retry_exhausted`
Keep `retry_exhausted`, but narrow its semantic meaning toward:
- retry budget exhausted
- no more retries allowed under policy

## 6.3 Keep `run_type`
No rename in this wave.

## 6.4 Keep `retry_of_run_id`
Continue using the explicit column as canonical lineage.

---

## 7. Scheduler and Worker Behavior

## 7.1 Worker
Worker continues to:
- finalize current run
- classify failure as retryable or not
- not create retry runs
- not own retry timing

No new ownership is moved to worker.

## 7.2 Scheduler
Scheduler continues to:
- evaluate retryable failed runs
- apply backoff
- create retry child runs
- mark source runs as retry-processed
- mark retry exhaustion where applicable

The change in this wave is that retry handling state becomes explicit instead of overloading `retry_exhausted`.

---

## 8. Serializer / API / UI Compatibility

## 8.1 Minimal outward churn
This wave should minimize surface churn in:
- history API
- scrape status compatibility surfaces
- scheduler UI
- existing filters

## 8.2 `finished`
Compatibility for `finished` remains on input/filter paths where required.

Outputs should prefer `success`.

## 8.3 Retry fields
Expose the new semantics carefully:
- adding `retry_processed` is allowed
- do not remove legacy fields abruptly
- keep compatibility behavior stable where possible

---

## 9. Repository-Aligned Implementation Boundaries

Expected touch points include:

- `pricewatch/db/models.py`
- Alembic migration(s)
- `pricewatch/db/repositories/scrape_run_repository.py`
- `pricewatch/scrape/scheduler.py`
- `pricewatch/scrape/worker.py` only where retryable persistence/status normalization touches it
- `pricewatch/web/serializers.py`
- `pricewatch/services/scrape_history_service.py` if compatibility/status projection requires it
- scheduler/history/status related tests

Optional lightweight helpers may be introduced to distinguish scheduler-owned vs legacy runs.

---

## 10. Acceptance Criteria

This RFC is considered implemented when:

1. `success` is the canonical completed-success status in implementation and serialization paths.
2. `finished` is retained only as compatibility input/filter behavior where needed.
3. `retry_processed` exists and is used for scheduler retry-handling progress.
4. `retry_exhausted` no longer needs to mean both “already handled” and “budget exhausted”.
5. `retry_of_run_id` remains the canonical retry lineage field.
6. attempt arithmetic matches:
   - `attempt=1` initial
   - `max_retries` = additional retries beyond the initial run.
7. code paths can distinguish scheduler-owned vs legacy runs through a lightweight rule.
8. API/UI compatibility remains intact or changes are explicitly limited and documented.

---

## 11. Deferred Topics

The following remain deferred:

- renaming `run_type`
- removing compatibility for legacy `finished` entirely
- full store-centric API cleanup
- table split between legacy and scheduler runs
- deep redesign of history/status/UI around run lineage visualization

---

## 12. Recommended Rollout

Recommended order:

1. schema/model clarification (`retry_processed`)
2. scheduler retry-state cleanup
3. repository/helper cleanup
4. serializer/history normalization
5. tests locking down semantics
6. docs/operator updates if needed

This keeps the change incremental and avoids broad compatibility churn.
