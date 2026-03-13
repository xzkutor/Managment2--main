# ADR-0007: Database-backed scrape runner and scheduling architecture

- **Status:** Proposed
- **Date:** 2026-03-13
- **Decision Makers:** Project maintainers
- **Related RFCs:** RFC-008 — Scheduler MVP
- **Supersedes:** None
- **Superseded by:** None

## 1. Context

The repository already separates several important concerns:

- shop-specific integration code lives behind the adapter/registry boundary under `pricewatch/shops/` and related services;
- network access has been consolidated behind canonical HTTP client abstractions under `pricewatch/net/`;
- web-facing orchestration lives under `pricewatch/web/` and SHOULD remain focused on request/response responsibilities rather than long-running scrape execution;
- the project has already adopted DB-first semantics for user-facing comparison and review flows as documented in ADR-0001.

That architectural direction creates a missing execution-plane requirement: the project needs a first-class way to run scraping and synchronization work outside request handling, including scheduled execution, manual execution, and future retry/backfill flows.

At present, without an explicit scrape execution architecture, the project risks drifting toward one or more of the following anti-patterns:

1. source-specific cron scripts outside the repository contract;
2. long-running scrape logic coupled to Flask routes or ad hoc CLI entrypoints;
3. weak or non-existent durable run history;
4. inconsistent retry behavior across sources;
5. accidental overlapping runs for the same logical job;
6. no stable operational surface for future admin/API/UI controls.

The project needs an architecture that is:

- consistent with the existing DB-first direction;
- compatible with the adapter registry boundary established by ADR-0004;
- implementable without introducing mandatory external queue/broker infrastructure in the first iteration;
- explicit about job configuration, scheduling, execution, and audit trail;
- extensible toward checkpoints, leases, cancellation, metrics, and operator tooling.

## 2. Decision

The project SHALL implement scrape orchestration as a **database-backed scheduler and database-backed run queue** with explicit separation between:

1. **ScrapeJob** — durable job definition describing what should be executed;
2. **ScrapeSchedule** — durable schedule policy describing when a job becomes due;
3. **ScrapeRun** — durable record of one concrete execution attempt;
4. **Runner** — typed execution unit that performs a scrape/sync action;
5. **Scheduler** — service that detects due jobs and enqueues runs;
6. **Worker** — service that claims queued runs and executes the appropriate runner.

The initial implementation SHALL use the application database as the source of truth for:

- job configuration;
- scheduling state;
- run lifecycle state;
- retry metadata;
- execution statistics;
- future checkpoint/lease metadata.

The initial implementation SHALL NOT require Redis, RabbitMQ, Celery, RQ, or another external task broker.

## 3. Rationale

### 3.1 Why this fits the repository

This repository is already moving toward explicit internal boundaries:

- shop-specific variability belongs inside adapters and adapter-facing services, not in top-level orchestration;
- HTTP/web code is being cleaned into dedicated web modules and compatibility layers;
- DB-first product behavior means scraping is an input pipeline to persisted normalized state, not part of end-user request rendering.

A database-backed scheduler preserves that direction. It keeps scrape execution as a separate operational plane while reusing the project’s existing persistence-oriented design.

### 3.2 Why not route-driven or cron-script orchestration

Embedding scrape execution directly in Flask request handlers would violate the current direction of the `pricewatch/web/` package and would mix user-facing request handling with long-running integration work.

Delegating the primary scheduling model to ad hoc system cron scripts would move important behavior outside the repository, weaken observability, and make job/run semantics harder to standardize across shops and environments.

### 3.3 Why not start with an external broker

A broker-based system may become appropriate later, but it would add infrastructure and operational cost before the repository has stabilized the domain model for scrape jobs, schedules, run states, and runner contracts.

The project’s immediate need is not maximal distributed throughput; it is a clear and durable execution model consistent with the repository’s existing architecture.

## 4. Architectural Rules Established by This ADR

### 4.1 Job, schedule, and run are distinct entities

The project SHALL treat the following as separate concepts:

- **job** = durable definition of what should run;
- **schedule** = durable definition of when the job is due;
- **run** = one concrete execution attempt.

These concepts MUST NOT be conflated in code, storage, or API semantics.

### 4.2 Every execution SHALL produce a durable run record

All manual and scheduled executions SHALL create a `ScrapeRun` record.

A run record is the authoritative audit artifact for scrape execution status.

### 4.3 Scheduler and worker responsibilities SHALL remain separate

The scheduler SHALL:

- find due jobs;
- evaluate scheduling eligibility;
- enforce no-overlap policy at enqueue time;
- create queued runs;
- compute/store the next due time.

The scheduler SHALL NOT perform source-specific scraping logic.

The worker SHALL:

- claim queued runs;
- resolve the appropriate runner implementation;
- execute the runner;
- persist run outcome and execution metadata.

The worker SHALL NOT decide schedule timing policy.

### 4.4 Runner dispatch SHALL be typed and registry-based

Runners SHALL be resolved by explicit runner type, not by scattered branching inside routes, scheduler code, or source-specific cron entrypoints.

This rule aligns scrape execution with the adapter-registry style integration boundary already established elsewhere in the repository.

### 4.5 No-overlap SHALL be the default policy

Unless a job explicitly allows overlap, the system SHALL prevent multiple active runs for the same logical job.

For MVP, “active” SHALL include at least:

- `queued`
- `running`

### 4.6 Retry behavior SHALL be explicit

Retry behavior SHALL be governed by job policy and error classification.

The project SHALL NOT rely on blind or implicit reruns without explicit run-state recording.

### 4.7 Execution state SHALL remain database-visible

Run lifecycle transitions SHALL be persisted and inspectable.

Operational tooling, admin/API surfaces, and future UI functionality SHALL build on these durable states rather than process-local memory.

## 5. Repository-aware Placement Guidance

The architecture introduced by this ADR is expected to fit the repository as follows.

### 5.1 New execution-plane modules

The implementation SHOULD introduce a dedicated scrape execution area under `pricewatch/`, for example:

```text
pricewatch/
  scraping/
    jobs/
    runners/
    execution/
    policies/
    services/
```

Exact filenames may vary, but the repository SHOULD keep:

- runner contracts and registry separate from shop adapters;
- scheduler/worker orchestration separate from Flask web handlers;
- persistence repositories for jobs/runs separate from runner implementations.

### 5.2 Existing package boundaries

- `pricewatch/web/` SHALL remain request/response oriented.
- `pricewatch/shops/` SHALL continue to own source-specific scraping and parsing behavior.
- `pricewatch/net/` SHALL remain the canonical home for transport/client abstractions used by runners.
- `pricewatch/services/` MAY host orchestration-facing services during transition, but the target model SHOULD avoid scattering scrape scheduling semantics across unrelated service modules.

### 5.3 Persistence alignment

The persistence model for jobs, schedules, and runs SHALL align with the project’s SQLAlchemy/Alembic direction and SHALL NOT introduce ad hoc file-based scheduling state as the primary source of truth.

## 6. Minimum Domain Model Implied by This ADR

The ADR does not freeze final schema details, but it establishes the minimum conceptual model.

### 6.1 ScrapeJob

A scrape job represents a durable execution definition.

Representative fields include:

- `id`
- `source_key`
- `runner_type`
- `params_json`
- `enabled`
- `priority`
- `allow_overlap`
- `timeout_sec`
- `max_retries`
- `retry_backoff_sec`
- `concurrency_key`
- `next_run_at`
- `last_run_at`

### 6.2 ScrapeSchedule

A scrape schedule represents when a job becomes due.

Representative fields include:

- `job_id`
- `schedule_type` (`cron`, `interval`, `manual`, `one_shot`)
- `cron_expr`
- `interval_sec`
- `timezone`
- `jitter_sec`
- `misfire_policy`

### 6.3 ScrapeRun

A scrape run represents one concrete execution attempt.

Representative fields include:

- `id`
- `job_id`
- `trigger_type` (`scheduled`, `manual`, `retry`, `backfill`)
- `status` (`queued`, `running`, `success`, `partial`, `failed`, `cancelled`, `skipped`)
- `attempt`
- `queued_at`
- `started_at`
- `finished_at`
- `worker_id`
- `error_message`
- `stats_json`
- `checkpoint_in_json`
- `checkpoint_out_json`

## 7. Lifecycle Model

### 7.1 Scheduled execution flow

1. Scheduler finds due jobs.
2. Disabled jobs are ignored.
3. Overlap policy is evaluated.
4. If eligible, a queued run is created.
5. The next due time is computed and stored.
6. A worker claims the queued run.
7. The worker resolves the runner and executes it.
8. Final run state and execution metadata are persisted.

### 7.2 Manual execution flow

1. An internal/admin/API action requests job execution.
2. The system creates a queued run with trigger type `manual`.
3. A worker claims and executes that run through the same runner pathway.

Manual execution SHALL use the same durable run model as scheduled execution.

## 8. Error Classification and Retry Rules

The project SHALL classify scrape execution failures conceptually into at least:

- **transient** — timeout, temporary upstream failure, rate limit, short-lived network error;
- **permanent** — invalid configuration, parser/selector bug, removed source structure, unsupported invariant violation;
- **policy/blocking** — forbidden access, anti-bot denial, explicit source blocking or policy refusal.

For MVP:

- transient failures MAY be retried according to job policy;
- permanent failures SHALL fail the run directly;
- policy/blocking failures SHALL fail the run directly unless a future RFC defines a distinct handling policy.

## 9. Consequences

### 9.1 Positive consequences

1. Scrape execution becomes a first-class operational subsystem inside the repository.
2. Scheduled and manual runs share one durable execution model.
3. Future admin/API/UI surfaces can rely on stable run history.
4. The design is consistent with DB-first product semantics.
5. The repository avoids premature dependency on external broker infrastructure.
6. Future hardening features such as leases, checkpoints, cancellation, metrics, and stale-run recovery fit naturally.

### 9.2 Negative consequences

1. The repository must implement and test DB-backed claim/lock semantics carefully.
2. The application database becomes part of execution coordination.
3. A future high-scale execution plane may still require a dedicated queue/broker.
4. The first implementation will add schema, services, and operational commands that do not exist today.

## 10. Alternatives Considered

### 10.1 Ad hoc system cron as the primary orchestration model

Rejected.

This would move critical scheduling behavior outside the repository, reduce visibility into run lifecycle, and make job semantics inconsistent across environments.

### 10.2 Direct route-triggered long-running scrape execution

Rejected.

This would violate package boundary discipline in `pricewatch/web/`, produce fragile request behavior, and blur the line between product-facing APIs and operational scraping work.

### 10.3 External broker/task framework from the start

Rejected for MVP.

This may become appropriate later, but it is premature before the repository formalizes scrape job/run domain semantics.

## 11. Non-goals

This ADR does not:

1. define the final SQLAlchemy model fields and indexes in full detail;
2. define concrete claim/lock SQL semantics;
3. define the full admin/API surface;
4. require distributed leader election in the first implementation;
5. require checkpoint/resume, cancellation, or heartbeat in MVP;
6. require replacing existing shop adapters or HTTP client abstractions.

## 12. Required Follow-up RFC

A follow-up RFC MUST define:

1. concrete schema for jobs, schedules, and runs;
2. state transition rules;
3. worker claim/lock behavior;
4. runner interface and registry contract;
5. retry and backoff rules;
6. minimal internal/admin API surface;
7. operational entrypoints/commands;
8. observability and metrics requirements;
9. migration strategy for any existing ad hoc sync entrypoints.

## 13. Acceptance Criteria

This ADR is considered implemented when all of the following are true:

1. the repository contains a durable job/schedule/run model for scrape orchestration;
2. scheduled and manual scrape execution both create durable run records;
3. scheduler logic is separated from runner execution logic;
4. runner dispatch is typed and registry-based;
5. no-overlap is enforced by default for jobs unless explicitly disabled;
6. scrape orchestration does not depend on route-bound long-running execution as the primary model;
7. the implementation works without requiring an external broker;
8. repository documentation reflects scrape runner and scheduling architecture as a first-class subsystem.

## 14. Final Statement

The repository will implement scrape orchestration as a **database-backed scheduler and database-backed run queue** with explicit separation between job definition, schedule policy, run history, runner execution, scheduler dispatch, and worker processing.

This decision establishes the architectural baseline for scheduled and manual scraping in the project and keeps the execution plane consistent with the repository’s existing DB-first and boundary-oriented direction.
