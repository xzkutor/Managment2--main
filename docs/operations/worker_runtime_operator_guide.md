# Worker / Runtime Operator Guide

## Purpose

This guide explains how to operate the PriceWatch runtime in its current multi-process model.

It focuses on the roles and day-to-day operator workflows for:

- web runtime
- scheduler runtime
- worker runtime

It also explains how to interpret runtime status, what "queued" means in practice, and how to diagnose common operational issues.

---

## Runtime Topology

The project uses three distinct runtime roles.

### 1. Web
Responsibilities:
- serves the UI
- serves admin/control-plane HTTP API
- serves scheduler/worker/queue status information

Production expectation:
- run with **Gunicorn**
- do **not** rely on Flask built-in server in production

### 2. Scheduler
Responsibilities:
- finds due jobs
- creates queued runs
- schedules retries with backoff
- does **not** execute scraping

Production expectation:
- run as **exactly one dedicated process**

### 3. Worker
Responsibilities:
- claims queued runs
- executes runners
- finalizes run results
- does **not** compute future timing
- does **not** create retry runs directly

Production expectation:
- run as **one or more dedicated processes**

---

## Development vs Production

## Development
Allowed:
- Flask built-in server
- embedded scheduler autostart, when enabled by configuration
- separate scheduler/worker processes for parity testing

Use this for:
- local development
- debugging
- feature work
- UI/API iteration

## Production
Required:
- Gunicorn for web
- one dedicated scheduler process
- one or more dedicated worker processes

Do **not**:
- use Flask built-in server as the production runtime
- rely on embedded scheduler autostart inside production web workers
- embed worker execution inside the web runtime

---

## Canonical Runtime Entry Points

These are the canonical process entry styles for the current runtime model.

## Web
Use Gunicorn against the Flask application entrypoint.

Typical pattern:
```bash
gunicorn app:app
```

Notes:
- the exact worker count is deployment-specific
- production may run with 1..N Gunicorn workers
- embedded scheduler autostart must remain disabled in production

## Scheduler
Use the dedicated scheduler module entrypoint.

Typical pattern:
```bash
python -m pricewatch.scrape.run_scheduler
```

## Worker
Use the dedicated worker module entrypoint.

Typical pattern:
```bash
python -m pricewatch.scrape.run_worker
```

---

## Runtime Configuration

The exact configuration surface may evolve, but the runtime currently centers around these concepts:

- `APP_ENV`
- `SCHEDULER_ENABLED`
- `SCHEDULER_AUTOSTART`
- `SCHEDULER_TICK_SECONDS`
- worker poll configuration
- testing/development guards

## Important policy rules

### `APP_ENV`
Treat `APP_ENV` as the explicit runtime mode marker.

Typical values:
- `development`
- `production`

### Embedded scheduler autostart
Embedded scheduler autostart is:
- allowed only in development or explicitly constrained single-process modes
- forbidden in production web runtime

### Worker runtime
Worker execution is never owned by the web runtime.

---

## How the system behaves

## Happy path

1. Web is running and serving UI/API.
2. Scheduler process is running.
3. Scheduler sees a due job.
4. Scheduler creates a queued `ScrapeRun`.
5. Worker process sees the queued run.
6. Worker claims it.
7. Worker executes the runner.
8. Worker finalizes the run.
9. If the failure is retryable, scheduler later creates a retry run according to backoff policy.

---

## Canonical operator status surface

For MVP, the canonical aggregated runtime status endpoint is:

```text
/api/scrape-status
```

This endpoint is the main operator-facing status surface.

It is expected to expose nested sections such as:

- `scheduler`
- `worker`
- `queue`
- optionally `runs` as compatibility/summary information

---

## How to read `/api/scrape-status`

The exact payload may evolve, but operators should interpret it conceptually like this.

## `scheduler`
Typical meaning:
- whether scheduler runtime is active in the current process context
- when it started
- when it last ticked
- what the last scheduler error was

Useful questions it answers:
- is the scheduler alive?
- is it ticking?
- did it fail recently?

## `worker`
Typical meaning:
- whether worker runtime is active in the current process context
- when it started
- when it last polled
- last claimed run
- last completed run
- last worker error

Useful questions it answers:
- is a worker process alive?
- is it polling?
- is it successfully claiming/finishing work?

## `queue`
Typical meaning:
- queued count
- running count
- maybe related summary counts

Useful questions it answers:
- is work piling up?
- are runs stuck in queued state?
- is there active execution?

## `runs`
If present, treat it as summary/compatibility data rather than the primary runtime liveness signal.

---

## Core operational scenarios

## Scenario 1: Scheduler UI shows jobs, but nothing runs
Check:
1. Is the scheduler process running?
2. Does `/api/scrape-status` show scheduler activity?
3. Are jobs actually due?
4. Are runs being created in `queued` state?
5. Is any worker process running?

Typical root causes:
- scheduler process not started
- schedule not due yet
- job disabled
- worker missing entirely

## Scenario 2: Runs are stuck in `queued`
This almost always means:
- worker is not running
- worker is not polling
- worker cannot claim work
- queue is growing faster than workers can consume it

Check:
1. `/api/scrape-status` → `worker`
2. `/api/scrape-status` → `queue`
3. recent scrape runs in the UI/admin history
4. worker process logs

Typical root causes:
- no worker process
- worker crashed
- worker misconfiguration
- claim path issue
- DB/session issue affecting claim/finalize flow

## Scenario 3: Scheduler is running, but retries do not appear
Check:
1. Was the failure marked retryable?
2. Did the job allow retries?
3. Has backoff time elapsed?
4. Is scheduler still ticking after the failed run?

Remember:
- worker does not create retry runs
- scheduler creates retry runs after backoff

## Scenario 4: Production web is running, but scheduler appears duplicated
In production this should not happen through supported configuration.

Check:
1. Is embedded scheduler autostart disabled in production?
2. Are you running Gunicorn with multiple web workers?
3. Did someone accidentally enable dev-style autostart in production?

Expected policy:
- production scheduler is one dedicated process only

## Scenario 5: Web works, but scrape system appears idle
Check:
1. Is the dedicated scheduler process running?
2. Is the dedicated worker process running?
3. Does `/api/scrape-status` show queue growth or scheduler activity?
4. Are jobs enabled and scheduled correctly?

Remember:
- web availability alone does not imply scheduler/worker availability

---

## Typical operating commands

These commands are examples. Adapt them to your environment, service manager, or deployment style.

## Start web
```bash
gunicorn app:app
```

## Start scheduler
```bash
python -m pricewatch.scrape.run_scheduler
```

## Start worker
```bash
python -m pricewatch.scrape.run_worker
```

If you use systemd, supervisor, Docker Compose, or another service manager, keep these as the canonical process payloads behind those wrappers.

---

## Recommended process model

## Development
A practical dev model may be:
- Flask dev server
- embedded scheduler autostart enabled
- optional dedicated worker process for testing

or, for higher parity:
- Flask dev server
- dedicated scheduler process
- dedicated worker process

## Production
Recommended:
- Gunicorn web
- exactly one dedicated scheduler process
- one or more dedicated worker processes

---

## Log interpretation guidance

At minimum, operators should expect useful logs around:
- scheduler startup
- scheduler tick failures
- worker startup
- worker claim/finalize failures
- queue activity anomalies

When debugging, correlate:
- web logs
- scheduler logs
- worker logs
- `/api/scrape-status`
- recent scrape runs in the UI/admin API

Do not rely on any single signal in isolation.

---

## What queued, running, success, and failed mean operationally

## `queued`
A run exists and is awaiting worker claim.

Operational meaning:
- scheduler did its job
- worker has not yet claimed the run

## `running`
A worker has claimed the run and is executing it.

Operational meaning:
- work is in flight
- check worker/runtime activity if it stays here unusually long

## `success`
The run completed successfully.

Operational meaning:
- scheduler + worker + runner path all worked for that run

## `failed`
The run completed unsuccessfully.

Operational meaning:
- inspect run details and worker logs
- determine whether failure was retryable
- remember retry scheduling is done by scheduler, not worker

---

## Common pitfalls

1. **Assuming web availability means scrape execution is healthy**
   - it does not
   - scheduler and worker are separate runtime concerns

2. **Running production web on Flask built-in server**
   - unsupported production pattern

3. **Letting production web autostart embedded scheduler**
   - risks duplicate schedulers under multi-worker serving

4. **Starting scheduler but forgetting worker**
   - results in queued runs piling up

5. **Expecting worker to create retries**
   - retries are scheduler-owned

6. **Treating `/api/scrape-status` as only a queue view**
   - it is a runtime visibility endpoint, not just a run-count endpoint

---

## Operational checklist

Before calling the system healthy in production, verify:

- web is running under Gunicorn
- scheduler dedicated process is running
- worker dedicated process is running
- `/api/scrape-status` shows healthy scheduler activity
- `/api/scrape-status` shows worker activity
- queue is not growing unexpectedly
- jobs are enabled as intended
- recent runs are completing as expected

---

## Escalation checklist for stuck execution

If work is not progressing:

1. Check web is reachable
2. Check `/api/scrape-status`
3. Check queued/running counts
4. Check scheduler process health
5. Check worker process health
6. Check recent scrape runs
7. Check scheduler logs
8. Check worker logs
9. Confirm APP_ENV / scheduler autostart policy
10. Confirm dedicated processes were actually started

---

## Current MVP limitations

The current runtime model intentionally does not yet include:
- multi-scheduler coordination
- leader election
- per-worker registry as a first-class subsystem
- external queue broker
- embedded production worker mode
- deep autoscaling policy

Operators should treat the current model as:
- explicit
- understandable
- production-usable
- but intentionally still simple

---

## Summary

Use this mental model:

- **Web serves**
- **Scheduler schedules**
- **Worker executes**

In production:
- Gunicorn serves the web app
- one dedicated scheduler process creates work
- one or more dedicated worker processes execute work

If runs are piling up in `queued`, look at the worker.  
If no queued runs appear for due jobs, look at the scheduler.  
If UI works but scrape execution does not, remember the web runtime is only one of the three runtime roles.
