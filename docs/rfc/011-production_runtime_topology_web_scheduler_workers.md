# RFC-011: Production Runtime Topology for Web, Scheduler, and Workers

- **Status:** Draft
- **Date:** 2026-03-13
- **Depends on:** ADR-0010 Production Runtime Topology for Web, Scheduler, and Workers

## 1. Summary

This RFC defines the runtime entrypoints and deployment model for the project in development and production environments.

The goal is to replace the implicit “Flask dev server as the main runtime” assumption with an explicit multi-process runtime model that separates:

- web serving;
- scheduling;
- scraping execution.

This RFC standardizes:

- the canonical production web runtime;
- dedicated scheduler runtime behavior;
- dedicated worker runtime behavior;
- development-mode convenience behavior;
- runtime status visibility;
- repository-aligned implementation scope.

## 2. Motivation

The repository now contains:

- a web UI and admin API;
- scheduler logic that enqueues due jobs;
- worker logic that executes queued runs;
- operator-facing scheduler UI and scrape status surfaces.

The built-in Flask server is no longer sufficient as the de facto runtime model because it does not provide:

- production-grade HTTP serving;
- explicit role separation;
- safe scheduler behavior under multi-process serving;
- clear operational control for scheduler and worker processes.

The project needs a canonical runtime topology that:

- preserves local development convenience;
- is explicit and safe in production;
- aligns with the existing repository structure under `pricewatch/web`, `pricewatch/scrape`, and `pricewatch/db`.

## 3. Goals

This RFC aims to:

- define canonical runtime roles and responsibilities;
- define canonical runtime entrypoints for web, scheduler, and worker;
- define development vs production behavior;
- define configuration expectations for runtime startup;
- define minimum runtime visibility requirements for operators;
- define repository-aligned implementation boundaries.

## 4. Non-goals

This RFC does not attempt to:

- introduce Redis, Celery, RabbitMQ, or any external queue broker;
- add leader election or distributed scheduler coordination;
- redesign retry ownership (retry remains scheduler-owned);
- redesign repository claim semantics (claim remains repository-owned);
- define Kubernetes-specific deployment manifests;
- define exhaustive systemd/supervisor/container recipes;
- add embedded production worker execution inside the web runtime;
- refactor the project to an application-factory architecture in this wave.

## 5. Runtime Roles

### 5.1 Web runtime

Responsibilities:

- serve UI and HTTP API;
- expose admin/control-plane endpoints;
- expose scrape and runtime status surfaces;
- remain free of worker execution loops.

Canonical production implementation:

- **Gunicorn** serving the Flask application.

Rules:

- production web runtime may use one or more Gunicorn workers;
- production embedded scheduler autostart is forbidden regardless of Gunicorn worker count;
- web runtime must not own worker execution;
- built-in Flask server is development-only.

### 5.2 Scheduler runtime

Responsibilities:

- compute due jobs;
- create queued runs;
- schedule retries with backoff;
- update scheduler runtime visibility.

Rules:

- production scheduler runs as **exactly one dedicated process**;
- scheduler does not execute scraping logic;
- scheduler remains the owner of retry timing.

### 5.3 Worker runtime

Responsibilities:

- claim queued runs;
- resolve the runner type;
- execute the runner;
- finalize run result and visibility metadata.

Rules:

- worker does not create future retry runs;
- worker does not compute scheduling timing;
- worker runtime is external to the web process;
- one or more worker processes are allowed;
- MVP worker visibility is aggregated, not full per-worker registry tracking.

## 6. Development vs Production Behavior

### 6.1 Development

Supported development modes:

- Flask built-in server for local development;
- optional embedded scheduler autostart for convenience;
- separate scheduler and worker processes for local parity testing.

Development notes:

- embedded scheduler is a development convenience mode;
- it is not the canonical production runtime model.

### 6.2 Production

Required production model:

- web served via Gunicorn;
- scheduler running as one dedicated process;
- workers running as one or more dedicated processes;
- no embedded scheduler autostart inside production web runtime.

## 7. Canonical Entrypoints

This RFC standardizes three runtime entrypoints.

### 7.1 Web entrypoint

Production web runtime must expose a stable Gunicorn target based on the existing Flask application.

This RFC does not require migration to an application factory in this wave.

### 7.2 Scheduler entrypoint

A dedicated Python module entrypoint must exist for the scheduler runtime.

Expected behavior:

- initialize config/runtime context as needed;
- enter the scheduler polling loop;
- emit startup and runtime status signals;
- terminate cleanly on process shutdown.

Wrapper scripts or service-manager commands may exist later as deployment conveniences, but the canonical entrypoint must exist as a Python module entrypoint.

### 7.3 Worker entrypoint

A dedicated Python module entrypoint must exist for the worker runtime.

Expected behavior:

- initialize config/runtime context as needed;
- enter the worker polling loop;
- claim queued runs via repository contract;
- emit startup and runtime status signals;
- terminate cleanly on process shutdown.

Wrapper scripts or service-manager commands may exist later as deployment conveniences, but the canonical entrypoint must exist as a Python module entrypoint.

## 8. Configuration Model

This wave introduces an explicit runtime-mode marker and a small centralized runtime config/helper.

### 8.1 Runtime mode

`APP_ENV` is the explicit runtime-mode marker.

Expected values:

- `development`
- `production`
- `test` or equivalent test-mode handling if already established in repository conventions

Critical rule:

- production runtime policy must not rely only on `DEBUG` or `TESTING` booleans.

### 8.2 Scheduler config expectations

The runtime model must support configuration for:

- `SCHEDULER_ENABLED`
- `SCHEDULER_AUTOSTART`
- `SCHEDULER_TICK_SECONDS`

Critical rule:

- production guard must override accidental embedded scheduler autostart, even if a permissive flag is set.

### 8.3 Worker config expectations

The runtime model must support configuration for:

- `WORKER_ENABLED`
- `WORKER_POLL_SECONDS`
- optional worker identifier/label if implementation chooses to expose one

### 8.4 Defaults

General requirements:

- defaults must be safe;
- production defaults must not accidentally enable embedded scheduler autostart in Gunicorn web workers;
- development defaults may preserve local convenience.

## 9. Runtime Visibility and Operator Status

For MVP, **`/api/scrape-status` is the canonical aggregated operator status endpoint**.

The runtime model must expose enough information for an operator to answer:

- is the scheduler running?
- when did it last tick?
- is a worker active?
- when did a worker last poll, claim, or finish work?
- are runs stuck in queued state?
- is the queue growing?

### 9.1 Visibility model

The visibility model for this wave is hybrid:

- **process-local runtime state** for liveness/activity signals;
- **DB-derived queue stats** for queue and execution summary.

### 9.2 Response shape

For MVP, `/api/scrape-status` should return nested sections:

- `scheduler`
- `worker`
- `queue`

Illustrative shape:

```json
{
  "scheduler": {
    "running": true,
    "started_at": "...",
    "last_tick_at": "...",
    "last_error": null
  },
  "worker": {
    "configured": true,
    "running": true,
    "last_poll_at": "...",
    "last_claimed_run_id": 123,
    "last_completed_run_id": 120
  },
  "queue": {
    "queued_count": 4,
    "running_count": 1,
    "failed_recent_count": 2
  }
}
```

The exact fields may vary, but the nested scheduler/worker/queue shape is required.

## 10. Repository-aligned Implementation Boundaries

Expected touch points for implementation:

- `app.py`
- `pricewatch/scrape/bootstrap.py`
- `pricewatch/scrape/scheduler.py`
- `pricewatch/scrape/worker.py`
- dedicated runnable entrypoint modules under `pricewatch/scrape/`
- a small centralized runtime config/helper under a repository-appropriate location
- `pricewatch/web/admin_routes.py`
- `pricewatch/db/repositories/scrape_run_repository.py` where queue stats or worker visibility require support
- tests for runtime topology, entrypoints, and scrape-status visibility

Preferred implementation principle:

- keep runtime role logic explicit and separated by entrypoint;
- avoid smuggling production scheduler or worker behavior into request-serving code paths.

## 11. Migration and Compatibility Expectations

This RFC does not require removing current development convenience behavior immediately.

Compatibility expectations:

- local development via Flask dev server remains available;
- guarded scheduler autostart may remain in development mode;
- existing scrape UI/admin flows remain functional;
- production guidance becomes stricter without breaking local workflows.

## 12. Acceptance Criteria

This RFC is considered implemented when:

1. Production web runtime has a documented canonical Gunicorn entrypoint.
2. Scheduler has a dedicated Python module entrypoint.
3. Worker has a dedicated Python module entrypoint.
4. Production deployment no longer relies on the built-in Flask server.
5. Production deployment no longer relies on embedded scheduler autostart in the web runtime.
6. Production guard prevents accidental embedded scheduler autostart even when permissive flags are set.
7. `/api/scrape-status` exposes nested `scheduler`, `worker`, and `queue` sections.
8. Worker visibility is operator-usable in aggregated MVP form.
9. Development mode remains usable without forcing production-only ergonomics.
10. Runtime-topology tests cover the required behavior.

## 13. Deferred Topics

The following remain intentionally deferred:

- multi-scheduler coordination;
- distributed leader election;
- external broker/queue integration;
- container-orchestrator-specific deployment recipes;
- full per-worker registry/tracking;
- cancellation semantics;
- checkpoint orchestration redesign;
- application-factory migration.
