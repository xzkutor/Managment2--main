# RFC-008 Addendum — Scheduler Follow-up Decisions

**Status:** Resolved  
**Date:** 2026-03-13  
**Parent:** RFC-008 Scrape Scheduler MVP  
**Scope:** Four follow-up policy decisions from the MVP review

---

## Decision 1 — Cron schedules use `ScrapeSchedule.timezone` semantics

### Policy (normative)

When `ScrapeSchedule.schedule_type == "cron"`:

- The `cron_expr` is interpreted **in the timezone specified by `ScrapeSchedule.timezone`**.
- `ScrapeSchedule.timezone` MUST be a valid IANA timezone name (e.g. `"UTC"`, `"Europe/Kyiv"`).
- An invalid timezone name MUST be rejected explicitly with a clear `ValueError`.
- `next_run_at` is always stored as **UTC** regardless of the schedule timezone.
- Interval schedules (`schedule_type == "interval"`) are not affected by `timezone`; they
  remain epoch-based and always advance relative to the current UTC time.

### Implementation location

`pricewatch/scrape/schedule.py` — `compute_next_run`, `advance_next_run`.

Use `zoneinfo.ZoneInfo` from the Python standard library.  
No other module may import the cron library (`croniter`) directly.

---

## Decision 2 — Manual enqueue respects `allow_overlap=False`

### Policy (normative)

When `POST /api/admin/scrape/jobs/<id>/run` is called:

- If `job.allow_overlap == False` and an active run (`status in ("queued", "running")`) already
  exists for the job, the endpoint MUST return **`409 Conflict`** with a JSON error body.
- If `job.allow_overlap == True`, manual enqueue is always allowed regardless of active runs.
- If no active run exists, manual enqueue is always allowed regardless of `allow_overlap`.

This policy mirrors the scheduler's overlap guard semantics.

### Implementation location

`pricewatch/web/admin_routes.py` — `api_manual_enqueue_job`.  
Overlap query stays repository-owned: use `has_active_run_for_job` from
`pricewatch/db/repositories/scrape_job_repository.py`.

---

## Decision 3 — PostgreSQL claim uses `FOR UPDATE SKIP LOCKED`

### Policy (normative)

`claim_next_queued_run` in `pricewatch/db/repositories/scrape_run_repository.py` MUST:

- For **PostgreSQL** backends: use `SELECT ... FOR UPDATE SKIP LOCKED` to provide
  atomic, race-free claiming in multi-worker deployments.
- For **other backends** (SQLite, etc.): fall back to the existing first-match strategy
  (no row-level locking).
- Callers in `pricewatch/scrape/worker.py` MUST NOT contain any backend-conditional logic.
  The dialect detection and branching is exclusively repository-owned.

### Implementation location

`pricewatch/db/repositories/scrape_run_repository.py` — `claim_next_queued_run`.

---

## Decision 4 — Retry runs are created only by the scheduler

### Policy (normative)

- The **worker** (`pricewatch/scrape/worker.py`) MUST NOT enqueue a retry run under any
  circumstances. The worker is execution-only.
- The **scheduler** (`pricewatch/scrape/scheduler.py`) is the single owner of retry
  enqueue semantics.
- The scheduler MAY create a new queued run with `trigger_type="retry"` only when ALL
  of the following conditions are met:
  1. The source run has `status == "failed"`.
  2. The source run has `retryable == True`.
  3. The source run has NOT been processed for retry yet (`retry_of_run_id` is null on
     any existing retry run for that source, or a `retry_processed` flag is set on the
     source run — whichever is implemented).
  4. The job's `max_retries` has not been exhausted.
  5. `retry_backoff_sec` has elapsed since `finished_at` of the source run.
- Scheduler MUST honor `ScrapeJob.retry_backoff_sec` before creating a retry run.
- Retry runs increment the `attempt` counter: `attempt = source_run.attempt + 1`.

### Implementation location

- `pricewatch/scrape/contracts.py` — `RunnerResult.retryable` field.
- `pricewatch/scrape/worker.py` — persist `retryable` on `ScrapeRun` via `complete_run`.
- `pricewatch/db/models.py` — `ScrapeRun.retryable`, `ScrapeRun.retry_of_run_id`.
- `pricewatch/db/repositories/scrape_run_repository.py` — `list_retry_candidates`.
- `pricewatch/scrape/scheduler.py` — retry candidate detection in `run_tick`.
- Alembic migration required for new `ScrapeRun` columns.

---

## Terminology Alignment

All implementation code MUST use the following names (no synonyms):

| Concept | Canonical name in code |
|---|---|
| Job definition | `ScrapeJob` |
| Schedule config | `ScrapeSchedule` |
| Execution record | `ScrapeRun` |
| Runner interface | `BaseRunner` |
| Runner input | `RunnerContext` |
| Runner output | `RunnerResult` |
| Scheduler loop fn | `run_tick` |
| Worker loop fn | `process_one` / `run_loop` |
| Overlap query | `has_active_run_for_job` |
| Retry candidates | `list_retry_candidates` |

