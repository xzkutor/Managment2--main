# RFC-009: Scheduler runtime autostart integration

- **Status:** Draft
- **Date:** 2026-03-13
- **Owners:** Project maintainers
- **Related ADRs:** ADR-0007 — Database-backed scrape runner and scheduling architecture; ADR-0008 — Autostart scheduler with the application runtime
- **Related Docs:** `autostart_scheduler_application_runtime.md`

## 1. Summary

This RFC defines the repository-aware implementation for starting the scheduler loop automatically with the Flask application runtime.

The goal is not to create a generic background-service framework. The goal is to make the repository’s existing scheduler execution path actually run in normal application startup, while remaining safe under tests, re-initialization, and configuration-driven disablement.

This RFC covers:

- scheduler startup ownership;
- config flags and defaults;
- bootstrap helper placement;
- idempotent startup behavior;
- background thread lifecycle for the embedded scheduler loop;
- basic observability of scheduler runtime state.

This RFC does **not** cover worker autostart.

## 2. Goals

This RFC establishes the work required to:

1. start the scheduler automatically during normal application startup when enabled by configuration;
2. avoid duplicate scheduler loops in one process;
3. keep scheduler startup outside `pricewatch/web/` request handling;
4. keep tests, migrations, and non-serving contexts safe;
5. expose enough runtime status to confirm whether the scheduler is running;
6. preserve the current scheduler code under `pricewatch/scrape/` rather than rebuilding it in `app.py`.

## 3. Non-Goals

This RFC does not:

1. autostart the worker loop;
2. solve cross-process scheduler leader election;
3. guarantee exactly-once scheduling across multiple WSGI workers;
4. introduce a general-purpose runtime plugin framework;
5. redesign the scheduling model, runner model, or run-state schema;
6. move scheduler logic into route handlers.

## 4. Repository-Aware Scope and Placement

### 4.1 New module

Add a dedicated runtime bootstrap helper:

- `pricewatch/scrape/bootstrap.py`

This module SHALL own:

- startup decision helpers;
- process-local started/running state;
- background thread creation;
- exception-safe loop wrapper;
- a lightweight runtime status snapshot.

### 4.2 Existing modules expected to change

- `app.py`
  - call the scheduler bootstrap helper from application startup/bootstrap code;
- `pricewatch/scrape/scheduler.py`
  - expose a loop-friendly function or reuse an existing loop entrypoint cleanly;
- `pricewatch/web/admin_routes.py`
  - optionally enrich an existing status endpoint with scheduler runtime state;
- tests under `tests/`
  - add coverage for startup semantics and config gating.

### 4.3 Boundaries that MUST remain stable

- `pricewatch/web/` MUST remain free of scheduler loop implementation details;
- `pricewatch/shops/` MUST remain the source-specific integration boundary;
- `pricewatch/db/repositories/` MUST remain the persistence boundary;
- `app.py` MAY initiate startup but MUST NOT become the scheduler implementation itself.

## 5. Functional Policy

### 5.1 Config flags

The implementation SHALL support the following canonical flags:

- `SCHEDULER_ENABLED` — whether embedded scheduler functionality is available;
- `SCHEDULER_AUTOSTART` — whether the app should attempt startup automatically;
- `SCHEDULER_TICK_SECONDS` — scheduler loop tick interval;
- `TESTING` — existing test context flag, if present, used to suppress autostart.

Recommended defaults:

- `SCHEDULER_ENABLED=true`
- `SCHEDULER_AUTOSTART=true` for local/dev and single-process deployments;
- `SCHEDULER_AUTOSTART=false` in tests by default;
- `SCHEDULER_TICK_SECONDS` small but non-aggressive, e.g. 5–30 seconds depending on current repo conventions.

Exact defaults may be tuned during implementation, but they must be centralized and documented.

### 5.2 Startup decision

The scheduler bootstrap helper SHALL attempt startup only when all required conditions hold.

Minimum decision rules:

1. scheduler is enabled by config;
2. autostart is enabled by config;
3. the app is not in a suppressed test context;
4. the scheduler has not already been started in the current process.

Optional additional rules MAY be used to avoid duplicate startup in Flask debug-reload situations, but they must remain localized to the bootstrap helper.

### 5.3 Runtime model

For this wave, the scheduler SHALL run in a **background daemon thread** started by the bootstrap helper.

The thread wrapper SHALL:

- log startup success/failure;
- repeatedly call the scheduler tick loop;
- catch and log loop exceptions without silently killing the process;
- record basic runtime state such as last successful tick timestamp.

### 5.4 Idempotency

The bootstrap helper SHALL maintain a process-local guard preventing duplicate scheduler thread creation.

Calling `start_scheduler_if_enabled(app)` multiple times in one process MUST be safe.

### 5.5 Observability

The implementation SHALL expose minimal runtime state, either through:

- an extension on an existing admin/status endpoint; or
- a lightweight dedicated runtime status helper consumed by that endpoint.

Minimum recommended fields:

- `scheduler_enabled`
- `scheduler_autostart`
- `scheduler_running`
- `scheduler_started_at`
- `scheduler_last_tick_at`
- `scheduler_last_error`

## 6. Detailed Design

### 6.1 `pricewatch/scrape/bootstrap.py`

Recommended public surface:

- `should_start_scheduler(app) -> bool`
- `start_scheduler_if_enabled(app) -> bool`
- `get_scheduler_runtime_status() -> dict[str, object]`

Recommended internal state:

- `_scheduler_thread`
- `_scheduler_started`
- `_scheduler_started_at`
- `_scheduler_last_tick_at`
- `_scheduler_last_error`
- lock/guard protecting thread creation

### 6.2 `app.py`

`app.py` SHALL invoke the bootstrap helper after application initialization is complete enough for scheduler code to access configuration and DB/session infrastructure, but before request traffic is considered the normal runtime state.

The exact hook depends on the current structure of `app.py`, but the implementation MUST keep the call site explicit and easy to find.

### 6.3 `pricewatch/scrape/scheduler.py`

The scheduler module SHOULD provide or retain a clear reusable loop contract, for example:

- `run_tick(...)`
- `run_loop(...)`

The bootstrap helper SHOULD call a loop-friendly API rather than reimplement timing logic.

### 6.4 Status API integration

If the repository already exposes scrape runtime/admin status, the preferred integration is to enrich that existing surface instead of adding a brand-new endpoint.

Repository-fit preference:

- keep scheduler runtime visibility adjacent to existing scrape status/admin views;
- avoid introducing a separate route just for one runtime flag unless necessary.

## 7. Test Strategy

The implementation SHALL add coverage for:

1. scheduler starts when enabled/autostarted;
2. scheduler does not start when disabled by config;
3. repeated startup attempts do not create duplicate scheduler threads;
4. test context suppresses autostart;
5. status helper reflects running/not-running state;
6. bootstrap helper can be called from app initialization safely.

The tests MUST avoid flaky timing dependence wherever possible.

## 8. Operational Notes

### 8.1 Single-process expectation for this wave

This RFC is most directly aimed at the repository’s current local/dev and simple serving model.

Multi-process deployments may still choose to disable embedded autostart and run scheduler ownership elsewhere. That deployment decision remains valid and is not contradicted by this RFC.

### 8.2 Logging expectations

At minimum, logs SHOULD show:

- scheduler startup attempted;
- scheduler started;
- scheduler skipped and why;
- scheduler loop exception and the exception summary.

## 9. Rollout Plan

Phase 1:

- add bootstrap helper;
- wire app bootstrap;
- add process-local idempotency;
- add status visibility;
- add tests.

Phase 2:

- validate behavior in real local/dev runtime;
- confirm no duplicate start on common app init paths;
- update docs/config examples.

## 10. Acceptance Criteria

The RFC is satisfied when all of the following are true:

1. starting the application with scheduler autostart enabled results in a live scheduler loop without a separate manual startup step;
2. repeated app initialization in one process does not create duplicate scheduler threads;
3. disabling autostart through config suppresses startup cleanly;
4. tests and non-serving contexts remain free of accidental scheduler startup;
5. operators can confirm scheduler runtime state via logs and/or admin status output.

## 11. Deferred Work

The following remain intentionally deferred:

- worker autostart;
- cross-process scheduler ownership/leader election;
- graceful shutdown coordination beyond daemon-thread semantics;
- advanced health probes and metrics;
- runtime cancellation and lease recovery.
