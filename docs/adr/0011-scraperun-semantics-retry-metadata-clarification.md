# ADR-0011 — ScrapeRun Semantics and Retry Metadata Clarification

**Status:** Accepted (Implemented — RFC-012, 2026-03-14)  
**Date:** 2026-03-14  
**Decision Makers:** Project maintainers  
**Scope:** `ScrapeRun` model semantics, retry-related metadata, run status semantics, and compatibility rules for history, status, scheduler, worker, and UI surfaces.

## Context

The project has evolved from a store-centric scrape history model into a scheduler/worker-based execution model with:

- `ScrapeJob`
- `ScrapeSchedule`
- `ScrapeRun`
- scheduler-owned retry orchestration
- worker-owned execution and retry classification
- operator-facing history and runtime status surfaces

As a result, `ScrapeRun` now carries both:
- legacy/manual scrape history concerns
- scheduler-era queue/execution concerns

This is acceptable for the current architecture, but several semantics have drifted and now require explicit clarification.

The main areas of ambiguity are:

1. `run_type` vs `trigger_type`
2. canonical success status vs legacy `finished`
3. retry linkage semantics
4. retry processing vs retry exhaustion semantics
5. `attempt` and `max_retries` interpretation
6. store-centric vs job-centric identity for runs

Without explicit clarification, the codebase risks:
- ambiguous status handling in API/UI/history
- misleading retry field naming
- duplicated sources of truth for retry linkage
- inconsistent future scheduler/worker changes
- operator confusion when reading run history and retry state

## Decision

The project adopts the following canonical semantics for `ScrapeRun`.

### 1. Canonical success status
`success` is the canonical completed-success status for scheduler-era run handling.

`finished` remains a legacy compatibility value only, and must not be treated as the canonical success status for new behavior.

### 2. Run initiation cause vs runner identity
`trigger_type` is the canonical field describing **how a run was initiated**, for example:
- scheduled
- manual
- retry

`run_type` remains the legacy/public field describing **what kind of runner/execution target the run represents**.

For current architecture purposes:
- `trigger_type` = initiation cause
- `run_type` = legacy/public runner identity

### 3. Canonical retry linkage
`retry_of_run_id` is the canonical retry parent linkage.

Retry parent/child relationships must not rely on `metadata_json` as the primary source of truth.

### 4. Retry processing semantics
The current overloaded use of `retry_exhausted` is recognized as semantically imperfect.

The target semantic model is:
- one concept for “retry handling already processed”
- one concept for “retry budget exhausted”

This ADR does not require the immediate schema rename by itself, but it explicitly rejects the long-term use of a single field to mean both.

### 5. Attempt semantics
`attempt=1` is the initial execution attempt.

Retries are additional attempts beyond the initial run.

`max_retries` is interpreted as the maximum number of additional retry attempts beyond `attempt=1`.

### 6. Scheduler-owned runs are job-centric
For scheduler-owned runs, `job_id` is the primary orchestration identity.

`store_id` remains valid as:
- optional target context
- legacy compatibility context
- store-scoped reporting/filtering aid where applicable

But scheduler-era run semantics are primarily job-centric, not store-centric.

## Decision Drivers

This decision is driven by the following goals:

- reduce semantic ambiguity in scheduler, worker, history, and serializer code
- preserve compatibility without letting legacy names control new behavior
- improve operator understanding of run and retry state
- keep API/UI/history stable while clarifying internal invariants
- prepare for future cleanup of retry field naming and status normalization

## Clarified Model

## 1. Status semantics

### Canonical statuses
The canonical status model for current execution semantics is:

- `queued`
- `running`
- `success`
- `partial`
- `failed`
- `cancelled`
- `skipped`

### Legacy compatibility
`finished` is retained only as a compatibility concept where legacy filters, tests, or response normalization still need it.

The system should move toward:
- canonical internal success = `success`
- explicit compatibility handling for `finished`

## 2. Run type semantics

### `trigger_type`
Represents the initiating cause:
- scheduled
- manual
- retry

This field answers:
- why did this run start?

### `run_type`
Represents the legacy/public runner identity.

This field answers:
- what kind of run/runner target is this?

Although the name is imperfect, this ADR preserves it for compatibility and clarifies its meaning instead of renaming it immediately.

## 3. Retry linkage semantics

### Canonical linkage
`retry_of_run_id` is the canonical parent reference for retry child runs.

### Non-canonical linkage
`metadata_json` may carry descriptive context, but must not be the authoritative retry linkage mechanism.

This avoids duplicate truth sources and keeps retry relationships queryable and explicit.

## 4. Retry handling semantics

The project recognizes two distinct concepts:

1. **retry processed / retry handled**
   - this run has already been evaluated by scheduler retry logic and should not produce another retry child from the same source run

2. **retry exhausted**
   - retry budget is no longer available under the applicable retry policy

The current implementation may still use a legacy field shape temporarily, but future cleanup must move toward these concepts being distinct.

## 5. Attempt semantics

The run attempt model is:

- initial run = `attempt=1`
- first retry = `attempt=2`
- second retry = `attempt=3`
- and so on

Under this model:
- `max_retries` counts additional retries only
- the initial attempt is not itself a retry

This ADR does not force the exact implementation expression, but all scheduler logic, tests, and docs must align with this semantic model.

## 6. Run identity semantics

### Legacy/store-centric runs
Older/manual/store-oriented runs may still rely heavily on:
- `store_id`
- historical run filtering
- store-centric history expectations

### Scheduler-owned runs
Scheduler-owned runs are primarily identified by:
- `job_id`
- `run_type`
- `trigger_type`
- attempt/retry lineage

Therefore:
- `job_id` is primary for orchestration semantics
- `store_id` is contextual, not primary

## Consequences

### Positive
- clearer scheduler, worker, history, and serializer semantics
- better basis for retry cleanup
- improved operator and developer understanding
- lower risk of future semantic drift
- preserves compatibility while defining a cleaner target model

### Negative
- legacy/public naming such as `run_type` remains imperfect
- compatibility code for `finished` still has to exist for some time
- schema and serializer cleanup may require multiple incremental waves

## Rejected Alternatives

### Alternative 1 — Rename everything immediately
Immediately rename:
- `run_type` -> `runner_type`
- remove `finished`
- replace retry fields in one large migration

Rejected because:
- too much compatibility churn in one wave
- higher risk to UI/history/tests
- not necessary to clarify semantics first

### Alternative 2 — Keep current ambiguity undocumented
Rejected because:
- semantic drift is already visible
- retry naming ambiguity will worsen over time
- future changes will become harder and less trustworthy

### Alternative 3 — Split `ScrapeRun` into separate legacy and scheduler tables now
Rejected for this wave because:
- current architecture can still evolve within one run table
- the problem is semantic ambiguity first, not immediate physical model separation

## Implementation Guidance

The follow-up RFC and implementation plan should cover:

1. status normalization rules
2. compatibility handling for legacy `finished`
3. retry linkage normalization around `retry_of_run_id`
4. replacement or clarification of overloaded retry fields
5. serializer/history/UI compatibility behavior
6. tests that lock down:
   - canonical `success`
   - compatibility `finished`
   - attempt arithmetic
   - retry parent linkage

## Acceptance Criteria

This ADR is considered implemented when:

1. canonical success semantics are explicitly `success` ✅
2. `finished` is treated as compatibility-only ✅
3. `trigger_type` and `run_type` are documented and handled according to their clarified roles ✅
4. `retry_of_run_id` is the canonical retry linkage ✅
5. retry handling vs retry exhaustion semantics are explicitly separated in docs and follow-up implementation ✅ (`retry_processed` introduced via RFC-012)
6. attempt/retry arithmetic is documented and consistently enforced ✅
7. scheduler-owned runs are treated as job-centric in implementation and documentation ✅ (`is_scheduler_owned` / `is_legacy_run` helpers)

## Implementation Notes (RFC-012, 2026-03-14)

The follow-up RFC-012 has been implemented.  Key changes:

- `retry_processed` field added to `ScrapeRun` (migration `e5f6a7b8c9d0`).
- `retry_exhausted` now exclusively means "budget truly exhausted".
- `retry_processed` is set by the scheduler once it has evaluated a source run.
- `DEFAULT_STATUS_FINISHED` now resolves to `RunStatus.SUCCESS`.
- `serialize_run` exposes all three retry-state flags.
- `is_scheduler_owned` / `is_legacy_run` helpers on `ScrapeRun`.
- `metadata_json` no longer duplicates `retry_of_run_id`.

## Follow-up Deferred Topics

- Rename `run_type` to `runner_type` (deferred to next wave).
- Remove compatibility for legacy `finished` entirely (deferred).
- Full store-centric API cleanup (deferred).
- Table split between legacy and scheduler runs (deferred).
