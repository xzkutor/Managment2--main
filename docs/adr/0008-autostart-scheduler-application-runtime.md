# ADR-0008: Autostart scheduler with the application runtime

- **Status:** Proposed
- **Date:** 2026-03-13
- **Decision Makers:** Project maintainers
- **Related RFCs:** RFC-009 — Scheduler runtime autostart integration
- **Related ADRs:** ADR-0007 — Database-backed scrape runner and scheduling architecture
- **Supersedes:** None
- **Superseded by:** None

## 1. Context

The repository now contains a scheduler/worker execution subdomain under `pricewatch/scrape/` and the corresponding durable state under `pricewatch/db/models.py` and `pricewatch/db/repositories/`.

That architecture solves the modeling problem for scrape jobs, schedules, and runs, but it does not by itself guarantee that scheduled work is actually executed in normal application runtime.

At present, the repository has a Flask entrypoint in `app.py`, web route composition under `pricewatch/web/`, and scheduler loop logic under `pricewatch/scrape/scheduler.py`. Without an explicit runtime integration decision, the system risks one or more of the following repository-specific failures:

1. scheduler logic exists in the repository but never starts in the serving process;
2. scheduler start behavior differs between environments because it depends on ad hoc manual launching;
3. duplicate scheduler loops appear under Flask debug reload, repeated app initialization, or multi-import paths;
4. tests, migrations, and maintenance commands accidentally start long-running background loops;
5. operator-visible scheduler status remains ambiguous, leading to "scheduler seems not running" incidents.

The project needs a runtime policy that is:

- explicit about **who owns scheduler startup**;
- compatible with the existing application bootstrap in `app.py`;
- conservative about duplicate startup and test safety;
- observable enough for operators to verify that the scheduler loop is alive;
- narrow enough that it does not silently expand into a general background-process framework.

## 2. Decision

The project SHALL support **config-gated autostart of the scheduler loop from the application runtime**.

The scheduler autostart decision establishes the following rules:

1. the **web application bootstrap** is responsible for attempting scheduler startup;
2. scheduler startup SHALL be routed through an explicit bootstrap helper under `pricewatch/scrape/`;
3. scheduler startup SHALL be **idempotent** within a given process;
4. scheduler startup SHALL be **disabled by configuration** in environments that do not want embedded scheduler execution;
5. scheduler startup SHALL be **suppressed by default in tests** and other non-serving contexts;
6. the application SHALL expose enough runtime observability to distinguish "scheduler configured off" from "scheduler intended to run but failed to start" and from "scheduler is running".

The first runtime autostart wave SHALL apply to the **scheduler loop only**.

The worker lifecycle is intentionally left out of this ADR and remains a separate operational policy decision.

## 3. Rationale

### 3.1 Why application runtime owns the startup attempt

The repository already has a concrete application assembly point in `app.py`. That location is the natural place to decide whether optional embedded runtime services should start.

Placing the startup attempt in application bootstrap keeps the decision inside the repository’s normal runtime path instead of requiring an external operator step just to make scheduled jobs function.

### 3.2 Why startup must remain explicit and config-gated

The repository also serves non-serving contexts: tests, migrations, local diagnostics, and maintenance flows. A background loop that starts implicitly on import would be unsafe and difficult to reason about.

Autostart must therefore remain **explicitly invoked** and **guarded by configuration**.

### 3.3 Why startup logic must not live in routes

`pricewatch/web/` is the request/response boundary. Embedding scheduler thread management in route modules or request handlers would violate the repository’s current separation of concerns and would make lifecycle behavior harder to reason about.

### 3.4 Why this ADR excludes worker autostart

The scheduler and worker have different operational characteristics.

- The scheduler decides **when** work should be enqueued.
- The worker decides **how** queued work is executed.

Autostarting both at once would silently commit the repository to a stronger single-process execution model than has been agreed. The safer incremental decision is to autostart the scheduler and leave worker runtime ownership to a later decision.

## 4. Architectural Rules Established by This ADR

### 4.1 Scheduler startup is bootstrap-owned

The startup attempt SHALL be initiated from application bootstrap, not from route handlers, repository modules, or import side effects.

### 4.2 Scheduler startup is helper-mediated

The web bootstrap MUST NOT directly instantiate ad hoc background threads inline in `app.py`.

Scheduler runtime lifecycle code SHALL be centralized in a dedicated helper module under `pricewatch/scrape/`, for example:

- `pricewatch/scrape/bootstrap.py`

### 4.3 Startup is idempotent within a process

Repeated application initialization in the same process MUST NOT create multiple scheduler loops.

A process-local guard is required.

### 4.4 Startup is configuration-gated

The repository SHALL use explicit config flags to decide whether startup is attempted.

The canonical flags for this wave SHOULD be:

- `SCHEDULER_ENABLED`
- `SCHEDULER_AUTOSTART`
- `SCHEDULER_TICK_SECONDS`

Equivalent names are acceptable only if they are standardized in one place and documented.

### 4.5 Non-serving contexts must remain safe

Tests, migrations, CLI utilities, and similar non-serving contexts MUST be able to import and initialize application code without unintentionally starting the scheduler loop.

### 4.6 Runtime state must be observable

The repository SHALL expose scheduler runtime status through at least one of:

- structured startup/skip/error logging;
- scheduler fields in an existing admin/runtime status endpoint;
- a lightweight runtime status object maintained by the bootstrap helper.

## 5. Repository-Aware Placement Guidance

### 5.1 New module

The preferred location for startup ownership is:

- `pricewatch/scrape/bootstrap.py`

Recommended responsibilities:

- `should_start_scheduler(app)`
- `start_scheduler_if_enabled(app)`
- process-local start guard
- background thread lifecycle wrapper
- runtime status snapshot/helper

### 5.2 Existing files expected to change

The following repository locations are expected integration points:

- `app.py` — invoke scheduler bootstrap helper during application startup;
- `pricewatch/scrape/scheduler.py` — expose a reusable loop entrypoint rather than inline-only logic;
- `pricewatch/web/admin_routes.py` and/or existing status surface — optionally expose scheduler runtime status;
- tests covering scheduler startup semantics.

### 5.3 Stable boundaries that must remain stable

This ADR does not change the following repository boundaries:

- `pricewatch/web/` remains the HTTP boundary;
- `pricewatch/shops/` remains the adapter/integration boundary;
- `pricewatch/net/http_client.py` remains the canonical network boundary;
- scheduler startup does not authorize placing site-specific logic in runtime bootstrap code.

## 6. Non-Goals

This ADR does not:

1. autostart workers by default;
2. introduce process supervision, leader election, or distributed coordination;
3. implement lease/heartbeat recovery;
4. define cancellation semantics;
5. guarantee exactly-once scheduling across multiple independent web processes;
6. replace external process managers when the deployment later chooses to run scheduler and worker separately.

## 7. Consequences

### 7.1 Positive consequences

- scheduled scraping becomes functional in ordinary application runtime without a separate manual scheduler start step;
- scheduler ownership becomes explicit and repository-local;
- duplicate-start behavior becomes testable rather than accidental;
- operator confidence improves because runtime state becomes visible.

### 7.2 Negative consequences

- the serving process now owns a background runtime concern;
- process-local idempotency is necessary and must be implemented carefully;
- autostart in multi-process deployments still requires deployment-specific thinking, even if the repository supports the startup path.

## 8. Acceptance Criteria for the Follow-up RFC

A follow-up RFC for this ADR MUST define:

1. exact config flags and defaults;
2. exact application bootstrap hook location in `app.py`;
3. process-local idempotency behavior;
4. Flask debug reload and test-safety rules;
5. background thread model and exception handling policy;
6. runtime observability surface;
7. rollout/testing strategy.

## 9. Decision Summary

The project will integrate scheduler startup into normal application runtime through a **config-gated, idempotent bootstrap helper invoked from app bootstrap**, while keeping worker lifecycle out of scope for this wave.
