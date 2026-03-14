# Glossary

## Adapter

A shop-specific integration component responsible for retrieving and shaping source data from an external store.

## Adapter registry

The mechanism that maps a shop/store identity to the adapter implementation used for sync operations.

## Candidate match

A runtime-only suggested relationship between products, derived heuristically.
A candidate match is not persisted as confirmed truth by default.

## Category

A store-scoped or domain-relevant grouping used to organize products for sync and comparison.

## Category mapping

A persisted relationship that connects categories across stores or to the reference comparison context.

## Comparison

The workflow that evaluates reference data against target-store data using persisted DB records and available mappings.

## Confirmed mapping

An operator-approved persisted mapping treated as authoritative application truth.

## DB-first

Architectural principle where the main product flow reads from already synchronized database records rather than live scraping during the user-facing comparison step.

## Gap item

A context-dependent result indicating a missing or unresolved assortment relationship in the gap-review workflow.
It is not equivalent to a permanent domain entity by itself.

## Gap status

Operator review state attached to a gap item context, typically involving implicit `new` and explicit reviewed states such as `in_progress` and `done`.

## Implicit `new`

Default gap-review state that may exist conceptually without requiring a persisted database row.

## Legacy/debug endpoint

A route retained for troubleshooting, migration support, or exploratory flows, but not intended as stable product contract.

## Product

A persisted representation of a shop item or normalized item record used in sync, mapping, and comparison flows.

## Product mapping

A persisted confirmed relationship between products across stores or between reference and target contexts.

## Reference product

The product used as the baseline or anchor during comparison.

## Scrape run

A recorded execution of a sync/import operation, usually containing timing, source/store scope, and result metadata.

**Run-kind distinction (RFC-012 §5.6):**
- *scheduler-owned run*: `job_id IS NOT NULL` — created and tracked by the scheduler (`is_scheduler_owned` helper).
- *legacy / manual run*: `job_id IS NULL` — created by direct API calls or old-style helpers (`is_legacy_run` helper).

**Status lifecycle:**
- Canonical success status: `success`.
- `finished` is a compatibility-only input/filter value retained for backward compat.
- Lifecycle: `queued` → `running` → `success` | `failed` | `partial` | `cancelled`.

**Retry-state flags (RFC-012 §5.4):**
- `retryable` — worker-set; marks the failed run as eligible for scheduler retry scheduling.
- `retry_processed` — scheduler-set; marks that the scheduler has evaluated this source run for retry.  Prevents duplicate retry children.
- `retry_exhausted` — scheduler-set; marks that the `max_retries` budget is truly exhausted.

**Trigger type vs run type (RFC-012 §5.2):**
- `trigger_type` = initiation cause (`scheduled` / `manual` / `retry`).
- `run_type` = legacy/public runner identity field.

**Attempt arithmetic (RFC-012 §5.5):**
- Initial run: `attempt=1`.
- `max_retries` = additional retries beyond the initial attempt.
- Example: `max_retries=1` allows exactly one retry child (`attempt=2`).

## Service/admin API

Operational endpoints used for sync control, mapping maintenance, review workflows, and history/maintenance views.

## Store

A source shop or comparison participant represented in the persistence layer and integration registry.
