# RFC-008: Scrape Scheduler MVP

- **Status:** Draft
- **Date:** 2026-03-13
- **Owners:** Project maintainers
- **Related ADRs:** ADR-0004 — Adapter registry as the integration boundary for shops; ADR-0007 — Scrape runner and scheduling architecture

## 1. Summary

This RFC defines the MVP implementation for scheduled and manual scrape execution in the current repository.

The MVP introduces a database-backed scheduler and run queue that can launch typed scrape runners on a schedule or on demand, without introducing an external broker.

In this repository, the scheduler is not a generic background-job framework. It is an application-specific orchestration layer for shop scraping that must remain aligned with the existing boundaries:

- `pricewatch/shops/` remains the external-site integration boundary;
- `pricewatch/net/` remains the HTTP/network boundary;
- `pricewatch/services/` remains the application/service orchestration layer;
- `pricewatch/web/` remains the HTTP/API boundary;
- scheduler-specific persistence and execution logic is introduced as a separate execution subdomain rather than folded into routes or ad hoc scripts.

This RFC does not introduce distributed orchestration, an external message broker, or a general-purpose task-processing subsystem.

## 2. Goals

This RFC establishes the work required to:

1. support scheduled scrape execution through a database-backed scheduler;
2. support manual triggering of the same scrape jobs through an internal/admin application surface;
3. separate durable job configuration from concrete execution records;
4. execute scrape logic through typed runners resolved from a registry;
5. persist run history and basic execution statistics;
6. prevent accidental overlap for jobs that are not explicitly re-entrant;
7. define repository-aware package placement for scheduler, runner, and run-state code;
8. provide a foundation for later checkpoints, lease recovery, cancellation, and metrics.

## 3. Non-Goals

This RFC does not:

1. introduce Celery, RQ, RabbitMQ, Redis, Kafka, or equivalent broker infrastructure;
2. implement distributed leader election for multiple schedulers;
3. implement full checkpoint/resume in the MVP;
4. implement advanced fairness, adaptive rate-limiting, or per-shop dynamic backpressure;
5. redesign shop adapter contracts in `pricewatch/shops/`;
6. move scrape execution into HTTP request lifecycles;
7. introduce a general-purpose platform for unrelated background jobs.

## 4. Repository-Aware Scope and Placement

The MVP SHALL fit the current repository boundaries and naming conventions.

### 4.1 New package area

Scheduler and runner orchestration code SHALL live under a dedicated scrape-execution package.

Recommended structure:

- `pricewatch/scrape/`
  - `models.py`
  - `repository.py`
  - `scheduler.py`
  - `worker.py`
  - `registry.py`
  - `context.py`
  - `result.py`
  - `errors.py`
  - `service.py`
  - `schedule.py`
  - `runners/`
    - `base.py`
    - `category_scan.py`
    - `product_scan.py`
    - `full_sync.py`

Equivalent sub-organization is acceptable if the same separation of concerns is preserved.

### 4.2 Existing boundaries that MUST remain stable

The MVP MUST preserve the following repository boundaries:

1. `pricewatch/shops/` continues to own site-specific parsing, pagination, identifiers, and scrape behavior details;
2. `pricewatch/net/http_client.py` remains the canonical HTTP client boundary;
3. `pricewatch/web/` remains responsible for request/response handling and must not embed scheduler loops or runner internals;
4. `pricewatch/services/` may orchestrate job creation or manual triggering but must not become the scheduler loop itself;
5. persistence changes must remain compatible with the repository's current SQLAlchemy/Alembic direction.

### 4.3 Explicit anti-patterns for this repository

The MVP MUST NOT:

1. place periodic scheduler loops inside Flask app startup code;
2. embed scrape runner logic directly in route handlers under `pricewatch/web/`;
3. bypass adapter boundaries by placing source-specific HTML logic in scheduler code;
4. reintroduce ad hoc execution through one-off source scripts as the primary architecture.

## 5. Functional Model

The scheduler MVP introduces three primary durable concepts.

### 5.1 ScrapeJob

`ScrapeJob` is the long-lived configuration record describing what should be scraped.

Minimum conceptual fields:

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
- `created_at`
- `updated_at`

A job is configuration, not an execution attempt.

### 5.2 ScrapeSchedule

`ScrapeSchedule` describes when a job becomes due.

Minimum conceptual fields:

- `id`
- `job_id`
- `schedule_type` (`interval`, `cron`, `manual`, `one_shot`)
- `cron_expr`
- `interval_sec`
- `timezone`
- `jitter_sec`
- `misfire_policy`
- `created_at`
- `updated_at`

`ScrapeSchedule` SHALL be materialized as a separate table in the MVP.

This is a normative repository rule, not a postponed preference. The implementation MUST preserve the job-versus-schedule split established by ADR-0007 and MUST NOT collapse schedule configuration into an embedded JSON/structured column for the initial rollout.

### 5.3 ScrapeRun

`ScrapeRun` is the durable record of one execution instance.

Minimum conceptual fields:

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
- `created_at`
- `updated_at`

Every scheduled or manual execution MUST create a run row.

## 6. Runner Model

Runners are typed execution units resolved from a registry.

The registry key SHALL be `runner_type` from `ScrapeJob`.

The runner layer MUST remain separate from schedule timing and queue-claim logic.

### 6.1 Base contract

The MVP SHALL define a base runner contract that accepts structured context and returns structured result.

Representative shape:

- `RunnerContext`
  - `run_id`
  - `job_id`
  - `source_key`
  - `runner_type`
  - `params`
  - `attempt`
  - injected collaborators such as logger, repository accessors, http client, and optional checkpoint state
- `RunnerResult`
  - `status`
  - `items_seen`
  - `items_changed`
  - `pages_processed`
  - `warnings`
  - `error`
  - `checkpoint`

Exact type definitions may vary, but the contract MUST stay explicit and typed.

### 6.2 Initial runner set

The MVP SHOULD start with a small runner set aligned with current shop flows.

Suggested initial types:

1. `category_scan`
2. `product_scan`
3. `full_sync`

Additional types MAY be added later as long as they use the same contract.

### 6.3 Boundary rule

Runners MAY orchestrate shop adapters and services, but they MUST NOT duplicate parsing rules already owned by `pricewatch/shops/`.

## 7. Scheduler Model

The scheduler is a loop that detects due jobs and creates queued runs.

### 7.1 Required behavior

For each due job, the scheduler SHALL:

1. ignore disabled jobs;
2. evaluate no-overlap policy;
3. create a queued run when eligible;
4. compute and persist the next scheduled time;
5. avoid embedding source-specific scrape logic.

### 7.2 Due-job selection

A job is due when:

- it is enabled; and
- its schedule is eligible; and
- `next_run_at <= now()` for schedule types that use next-run timestamps.

The exact query may differ by backend, but due-job selection MUST be deterministic and testable.

### 7.3 Overlap policy

`allow_overlap` SHALL default to `false`.

If overlap is not allowed, the scheduler MUST NOT enqueue a new run for a job that already has an active run.

For MVP, “active run” means at least:

- `queued`
- `running`

### 7.4 Misfire policy

The MVP SHALL use a **single-step** misfire policy.

If a job is overdue, the scheduler MAY enqueue at most one new run for that job in a scheduler tick and SHALL then advance the schedule once.

The scheduler MUST NOT attempt backlog catch-up by creating multiple queued runs for the same overdue job in a single tick.

This rule is required for MVP in order to avoid queue floods after downtime and to reduce the risk of burst traffic against upstream shops.

### 7.5 Schedule computation and cron handling

The MVP SHALL support:

1. `interval`
2. `cron`
3. `manual`
4. `one_shot`

Cron schedule computation SHALL use a well-known external library wrapped behind repository-local scheduler abstractions.

The rest of the repository MUST NOT depend directly on the chosen cron library API. Cron parsing and `next_run_at` computation SHALL remain localized to scheduler-local modules such as `pricewatch/scrape/schedule.py` or an equivalent package-local service.

The MVP SHALL document the accepted cron syntax and timezone behavior. The initial cron posture is minute-level scheduling without a seconds field.

## 8. Worker Model

The worker is responsible for claiming queued runs and executing the appropriate runner.

### 8.1 Required behavior

The worker SHALL:

1. atomically claim a queued run;
2. mark it `running` with `started_at` and `worker_id`;
3. resolve the runner through the registry;
4. execute the runner;
5. persist final run status and result metadata.

### 8.2 Failure handling

The worker MUST distinguish between:

1. transient failures that may be retried later;
2. permanent failures that fail the run directly;
3. unexpected internal exceptions that fail the run and are recorded.

For MVP, retry policy SHALL be represented in model and service flow, but full delayed-retry scheduling MAY be deferred.

The first safe rollout MAY persist retry metadata and classify retryable failures without immediately implementing a dedicated delayed-retry queue.

### 8.3 Claim semantics

The worker claim path SHALL be repository-owned.

Callers outside scrape repository infrastructure MUST depend only on a narrow contract such as:

- `claim_next_queued_run(worker_id) -> ScrapeRun | None`

Backend-specific claim behavior MUST remain hidden behind this repository contract.

For PostgreSQL, the preferred implementation strategy is `SELECT ... FOR UPDATE SKIP LOCKED` or an equivalent row-locking claim pattern.

For simpler or less capable backends, a constrained optimistic-claim fallback is acceptable, provided it remains repository-local and is covered by tests.

Scheduler code, worker business logic, routes, and runners MUST NOT encode backend-specific claim semantics directly.

## 9. State Model and Allowed Transitions

The MVP SHALL define an explicit run-state model.

Minimum states:

- `queued`
- `running`
- `success`
- `partial`
- `failed`
- `cancelled`
- `skipped`

Allowed transitions for MVP:

1. `queued -> running`
2. `queued -> skipped`
3. `running -> success`
4. `running -> partial`
5. `running -> failed`
6. `running -> cancelled`

Unexpected or illegal transitions MUST be rejected by service/repository logic or at minimum covered by tests.

## 10. Persistence and Migration Expectations

The MVP SHALL follow the repository's current DB-first and Alembic-aware direction.

### 10.1 Database authority

Scheduler persistence MUST be represented through the shared ORM/migration model rather than ephemeral in-memory state.

### 10.2 Migration requirement

Schema for `scrape_jobs`, `scrape_schedules`, and `scrape_runs` SHALL be added via Alembic migration in the same manner as other durable application tables.

### 10.3 Cross-backend posture

The MVP MAY use backend-specific queue semantics where required, but such divergence MUST remain localized to scrape repository infrastructure rather than leak into runners, routes, or unrelated services.

The external contract observed by scheduler and worker code MUST remain backend-agnostic.

## 11. API and Admin Surface

The MVP SHALL provide a minimal operational surface for inspection and manual trigger.

Recommended internal/admin endpoints:

- `GET /api/admin/scrape/jobs`
- `POST /api/admin/scrape/jobs`
- `PATCH /api/admin/scrape/jobs/<id>`
- `POST /api/admin/scrape/jobs/<id>/run`
- `GET /api/admin/scrape/runs`
- `GET /api/admin/scrape/runs/<id>`

Exact path naming may follow existing admin-route conventions, but the capabilities above should be present.

### 11.1 Route responsibility

Routes in `pricewatch/web/` SHALL:

- validate request payloads;
- delegate to scheduler/job services;
- return serialized job/run data.

Routes SHALL NOT:

- execute long-running scrape logic inline;
- host polling loops;
- resolve shop adapters directly for scheduled execution.

### 11.2 Manual trigger surface

Manual triggering in MVP SHALL be internal/admin only.

The first rollout MUST NOT expose scrape-job execution as a public API surface.

## 12. CLI / Process Model

The MVP SHOULD support explicit process entrypoints for scheduler and worker execution.

Recommended examples:

- `python -m pricewatch.scrape.scheduler`
- `python -m pricewatch.scrape.worker`

Equivalent Flask/Click commands are acceptable if they preserve process separation.

The repository SHOULD avoid making scheduler execution depend on serving web requests.

## 13. Observability and Audit Requirements

The MVP MUST preserve basic operational visibility.

### 13.1 Persistent audit fields

The following MUST be inspectable after execution:

- trigger type;
- final status;
- timestamps;
- worker id;
- error message where relevant;
- basic execution statistics.

### 13.2 Basic metrics/logging

The MVP SHOULD emit logs for:

1. run queued;
2. run claimed;
3. run started;
4. run completed;
5. run failed.

Metrics MAY be deferred, but the result model should leave room for later counters/timers.

## 14. Testing Requirements

The MVP SHALL include tests that verify the orchestration contract, not only runner internals.

Minimum required test areas:

1. due-job selection logic;
2. no-overlap enforcement;
3. queued-run creation;
4. worker claim semantics;
5. runner dispatch through registry;
6. run-state transitions;
7. manual trigger flow;
8. failure recording for runner errors;
9. single-step misfire behavior;
10. cron/interval next-run calculation behavior.

Repository-aware tests SHOULD live alongside the current testing strategy and not rely solely on manual verification.

## 15. Implementation Phases

### Phase 1: Data model and repository scaffolding

Objectives:

1. introduce durable job/schedule/run models;
2. add repository methods for due-job lookup, active-run detection, queued-run creation, and run completion;
3. add migration scaffolding.

Deliverables:

- ORM models;
- Alembic migration;
- repository tests for core persistence behavior.

### Phase 2: Runner contract and registry

Objectives:

1. define context/result types;
2. add base runner contract;
3. register initial runner types.

Deliverables:

- runner base;
- runner registry;
- initial stub/real runners aligned with current shop flows.

### Phase 3: Scheduler loop

Objectives:

1. enqueue due jobs;
2. enforce overlap rules;
3. advance next-run timestamps consistently;
4. implement single-step misfire handling;
5. centralize schedule computation behind scheduler-local abstraction.

Deliverables:

- scheduler service/loop;
- schedule computation tests;
- no-overlap tests;
- misfire policy tests.

### Phase 4: Worker loop

Objectives:

1. claim queued runs;
2. execute registry-resolved runners;
3. persist final state and stats;
4. classify retryable versus terminal failures.

Deliverables:

- worker service/loop;
- run transition tests;
- failure-path tests;
- repository-backed claim tests.

### Phase 5: Manual trigger and inspection surface

Objectives:

1. allow internal/admin manual triggering;
2. expose job/run history for inspection;
3. document operational usage.

Deliverables:

- minimal admin/API routes;
- serializer coverage for job/run responses;
- operational documentation.

## 16. Risks

### 16.1 Claim/lock correctness risk

Incorrect queue-claim behavior can produce duplicate execution or stranded queued runs.

This risk is mitigated by explicit repository tests and a narrow claim path.

### 16.2 Boundary erosion risk

Without discipline, scheduler or runner code may start absorbing shop-specific parsing logic or route-specific request handling.

This risk is mitigated by preserving the adapter and web boundaries already established in the repository.

### 16.3 Long-running recovery gap

The MVP does not fully solve stale-run recovery, leases, or crash-resume behavior.

This is acceptable for MVP but must be captured as deferred work.

### 16.4 Schedule semantics drift risk

Cron/interval semantics can become inconsistent if next-run calculation and misfire behavior are not specified clearly.

This risk is mitigated by using a wrapped external cron library, documenting accepted syntax, and testing one explicit initial misfire policy.

## 17. Deferred Work

The following items are explicitly deferred beyond the MVP unless they are needed to complete the first safe rollout:

1. heartbeat and lease expiry;
2. stale-run recovery;
3. checkpoint/resume;
4. cancellation API and cooperative cancellation;
5. per-source concurrency quotas;
6. backfill orchestration;
7. richer metrics and dashboards;
8. external broker integration.

The model MAY carry fields such as `concurrency_key` or timeout metadata early, but enforcement beyond per-job no-overlap is deferred.

## 18. Acceptance Criteria

This RFC is considered implemented for MVP when all of the following are true:

1. durable tables/models exist for jobs, schedules, and runs;
2. `scrape_schedules` exists as a first-class table rather than embedded job JSON;
3. a scheduler loop can enqueue due jobs without running scrape logic itself;
4. a worker loop can claim queued runs through a repository-owned claim path and dispatch typed runners;
5. no-overlap is enforced by default on a per-job basis;
6. the scheduler uses a single-step misfire policy;
7. every manual and scheduled execution produces a durable run record;
8. basic run status, timestamps, and error details are inspectable;
9. manual triggering is possible only through an internal/admin application surface in the MVP;
10. repository tests cover the core orchestration behavior, including claim semantics and next-run calculation.

## 19. Resolved Questions

The following design questions are considered resolved for MVP and SHALL NOT remain implementation-time ambiguity:

1. `ScrapeSchedule` is a separate table in the MVP.
2. Cron parsing uses an external library wrapped by scheduler-local abstraction.
3. Worker claim semantics are repository-owned and may use backend-specific implementation hidden behind one contract.
4. Misfire policy for MVP is single-step enqueue-and-advance.
5. Manual trigger is internal/admin only.
6. Retry scheduling beyond basic metadata and classification is deferred unless required to complete the first safe rollout.

## 20. Remaining Deferred Decisions

The following areas remain intentionally deferred and do not block MVP implementation:

1. lease and heartbeat recovery semantics;
2. cancellation semantics and cooperative interruption contract;
3. checkpoint/resume protocol;
4. per-source concurrency quota enforcement;
5. retry re-enqueue timing model beyond persisted metadata and basic classification.

## 21. Decision Summary

The repository will add a scrape-scheduler MVP as a database-backed orchestration layer with explicit job, schedule, and run records; typed runner dispatch; process-separated scheduler and worker loops; repository-owned claim semantics; single-step misfire handling; and minimal internal/admin control.

The implementation must preserve the existing repository boundaries around web routes, HTTP client access, shop adapters, and service orchestration.
