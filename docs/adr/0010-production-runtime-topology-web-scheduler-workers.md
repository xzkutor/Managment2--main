# ADR-0010: Production Runtime Topology for Web, Scheduler, and Workers

- **Status:** Proposed
- **Date:** 2026-03-13
- **Deciders:** Project maintainers
- **Related RFC:** RFC-011 Production Runtime Topology for Web, Scheduler, and Workers

## Context

The project has evolved beyond a simple Flask application serving HTTP requests.

The repository now contains:

- a web UI and admin API under `pricewatch/web/`;
- scheduler logic that computes due jobs and enqueues scrape runs;
- worker logic that claims queued runs and executes runners;
- operator-facing scheduler and scrape status surfaces;
- runtime concerns that differ substantially between local development and production deployment.

The built-in Flask development server remains useful for local development, but it is not an appropriate production runtime for a system that now includes:

- multiple runtime roles;
- background polling loops;
- queue processing;
- explicit operator workflows;
- the need for predictable restart, scaling, and observability behavior.

An embedded background loop inside a web process also creates production risks:

- scheduler duplication when HTTP serving scales to multiple processes;
- unclear ownership between HTTP request handling and background execution;
- fragile observability and restart semantics;
- accidental coupling of operator and serving concerns.

The project therefore needs an explicit production runtime topology that separates runtime roles while preserving a convenient local-development mode.

## Decision

The project adopts a **multi-process runtime topology** with three distinct runtime roles:

1. **Web runtime**
   - serves the UI and HTTP API;
   - is the canonical production HTTP surface;
   - does not own worker execution.

2. **Scheduler runtime**
   - computes due jobs;
   - enqueues scrape runs;
   - schedules retries with backoff;
   - does not execute scraping.

3. **Worker runtime**
   - claims queued runs;
   - executes runners;
   - finalizes run results;
   - does not compute future scheduling or retries.

## Runtime Policy

### Production

- **Gunicorn** is the canonical production web runtime.
- The built-in Flask server is **not** a production runtime.
- The production scheduler runs as **exactly one dedicated process**.
- Production workers run as **one or more dedicated processes**.
- Embedded scheduler autostart in the web runtime is **forbidden in production**, regardless of Gunicorn worker count.
- The web runtime must never own worker execution.

### Development

- The built-in Flask server remains supported for local development.
- Embedded scheduler autostart may remain available in development or explicitly constrained single-process modes as a convenience.
- Development convenience behavior must not redefine the production runtime model.

## Architectural Rules

1. **Production web runtime uses Gunicorn.**
2. **Production scheduler is a dedicated single process.**
3. **Production workers are dedicated external processes.**
4. **Embedded scheduler autostart is dev-only or explicitly constrained, never canonical production behavior.**
5. **Web runtime never owns worker execution.**
6. **Retry orchestration remains scheduler-owned.**
7. **Queue claim semantics remain repository-owned.**
8. **Runtime entrypoints must exist as Python module entrypoints.**
9. **The canonical aggregated operator status endpoint for MVP is `/api/scrape-status`.**
10. **Production web runtime may use one or more Gunicorn workers, but embedded scheduler autostart remains forbidden in production regardless of worker count.**

## Consequences

### Positive

- clear separation of runtime ownership;
- production-safe web serving model;
- no accidental scheduler duplication from web-worker scaling;
- explicit operator model for scheduler and worker lifecycles;
- safer restart and observability semantics;
- ability to scale web and worker roles independently.

### Negative

- more processes must be managed;
- deployment documentation becomes more important;
- dedicated entrypoints and runtime-specific config are required;
- the project must define worker visibility explicitly rather than inferring all behavior from the web runtime.

## Accepted Scope Boundaries

This ADR intentionally supports:

- Gunicorn for production web serving;
- dedicated scheduler process in production;
- dedicated worker processes in production;
- development-only Flask server usage;
- development convenience embedded scheduler autostart under explicit guard;
- separate runtime visibility for scheduler/worker/queue.

This ADR intentionally does **not** decide:

- distributed leader election;
- multi-scheduler coordination;
- external brokers such as Redis, RabbitMQ, or Celery;
- Kubernetes-native deployment shape;
- per-worker runtime registry for MVP;
- application-factory refactor in this wave.

## Repository Alignment

This decision aligns with the repository’s current structure:

- `app.py` as composition/bootstrap layer;
- `pricewatch/web/` as HTTP/UI layer;
- `pricewatch/scrape/` as scheduler/worker/orchestration layer;
- `pricewatch/db/` as persistence layer.

The decision explicitly avoids smuggling production execution behavior into request-serving code paths.

## Follow-up Required

A follow-up RFC must define:

- runtime entrypoints;
- development vs production startup rules;
- runtime configuration boundaries;
- `/api/scrape-status` runtime visibility contract;
- implementation touch points and tests;
- deployment-aligned implementation constraints.

## Decision Summary

The project will use:

- **Gunicorn** as the canonical production web runtime;
- **one dedicated scheduler process** in production;
- **one or more dedicated worker processes** in production;
- **Flask built-in server only for development**;
- **embedded scheduler autostart only as guarded dev convenience**;
- **no worker execution inside the web runtime**.
