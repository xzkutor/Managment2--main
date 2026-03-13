# Scrape Scheduler MVP — Operations Guide

**Package:** `pricewatch/scrape/`  
**API entrypoint:** `pricewatch/web/admin_routes.py` (`/api/admin/scrape/…`)  
**DB persistence:** `pricewatch/db/models.py` — `ScrapeJob`, `ScrapeSchedule`, `ScrapeRun`  
**Alembic migration:** `migrations/versions/c3d4e5f6a7b8_scrape_scheduler_mvp.py`

---

## Architecture overview

```
┌────────────┐   list_due_jobs    ┌────────────────┐
│  Scheduler │ ──────────────────▶│  scrape_jobs   │
│  run_tick  │ ◀── enqueue_run ── │  scrape_runs   │
└────────────┘                    └────────────────┘
                                        │ claim
┌────────────┐  claim_next_queued ──────┘
│   Worker   │ ──────────────────▶ dispatch runner_type
│ process_one│ ──── BaseRunner.run(ctx) ────▶ SyncService
└────────────┘
```

### Key packages

| Package / module | Responsibility |
|---|---|
| `pricewatch/scrape/contracts.py` | `RunnerContext`, `RunnerResult`, `BaseRunner` |
| `pricewatch/scrape/registry.py` | Runner class dispatch by `runner_type` |
| `pricewatch/scrape/schedule.py` | `compute_next_run`, `advance_next_run` (wraps croniter) |
| `pricewatch/scrape/scheduler.py` | Due-job detection → `enqueue_run`, advance `next_run_at` |
| `pricewatch/scrape/worker.py` | Queue claim → runner dispatch → persist outcome |
| `pricewatch/scrape/runners.py` | Adapter runners over `CategorySyncService`, `ProductSyncService` |

---

## Job model

| Field | Description |
|---|---|
| `source_key` | Logical identifier for the shop/source |
| `runner_type` | Selects which `BaseRunner` subclass executes the job |
| `params_json` | Job-specific parameters passed to the runner via `RunnerContext.params` |
| `enabled` | When false, job is never enqueued by the scheduler |
| `priority` | Higher = picked first by `list_due_scrape_jobs` |
| `allow_overlap` | If false, scheduler skips if an active run already exists |
| `timeout_sec` | Soft timeout hint (enforcement deferred to future release) |
| `max_retries` | Maximum retry attempts (execution deferred to future release) |
| `next_run_at` | Next scheduled UTC time; updated after each tick |
| `last_run_at` | Last time the scheduler fired a run for this job |

---

## Schedule model

| Field | Description |
|---|---|
| `schedule_type` | `"interval"` or `"cron"` |
| `cron_expr` | Cron expression (used when `schedule_type == "cron"`) |
| `interval_sec` | Interval in seconds (used when `schedule_type == "interval"`) |
| `timezone` | IANA timezone name for cron evaluation (default `"UTC"`) |
| `jitter_sec` | Maximum random jitter added to computed next_run |
| `misfire_policy` | `"skip"` (MVP default): advance once, no backlog explosion |

---

## Run lifecycle

```
queued  →  running  →  success
                    →  partial
                    →  failed
        →  skipped    (scheduler skip — no run created)
        →  cancelled  (future: explicit cancellation)
```

### Legacy status compat

`ScrapeRun.status = "finished"` (used by pre-scheduler manual sync flows) is
treated as equivalent to `"success"` wherever status filtering is applied via
`ScrapeHistoryService`.

---

## No-overlap rule

By default (`allow_overlap = False`), the scheduler will NOT enqueue a new run
for a job if there is already a `queued` or `running` run for that job.

The scheduler still advances `next_run_at` when it skips an overlapping job,
so the next window is correctly computed.

To allow concurrent runs for a job, set `allow_overlap = True`.

---

## Manual trigger semantics

`POST /api/admin/scrape/jobs/<job_id>/run` enqueues a run with
`trigger_type = "manual"`.  The run enters the same `queued` state and is
processed by the same worker loop.  Manual triggers do NOT bypass the worker path.

---

## Registered runner types (MVP)

| `runner_type` | Class | Required params |
|---|---|---|
| `store_category_sync` | `StoreCategorySyncRunner` | `store_id` |
| `category_product_sync` | `CategoryProductSyncRunner` | `category_id` |
| `all_stores_category_sync` | `AllStoresCategorySyncRunner` | _(none)_ |

To add a new runner: subclass `BaseRunner`, set `runner_type`, decorate with
`@register_runner` in `pricewatch/scrape/runners.py` (or a separate module
that is imported at app startup).

---

## Scheduler and worker deployment

The MVP scheduler and worker loops live in `pricewatch/scrape/scheduler.py`
and `pricewatch/scrape/worker.py`.

### Minimal background thread wiring

```python
import threading
import time
from pricewatch.scrape.scheduler import run_tick
from pricewatch.scrape.worker import run_loop
from pricewatch.db.config import session_scope, get_session_factory

def scheduler_loop(session_factory, tick_interval_sec=60):
    while True:
        session = session_factory()
        try:
            run_tick(session)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
        time.sleep(tick_interval_sec)

# Start in background threads:
factory = get_session_factory()
threading.Thread(target=scheduler_loop, args=(factory,), daemon=True).start()
threading.Thread(target=run_loop, args=(factory,), daemon=True).start()
```

---

## API endpoints (scheduler control-plane)

All endpoints require no auth in MVP (same as existing admin API).

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/admin/scrape/jobs` | List jobs |
| `POST` | `/api/admin/scrape/jobs` | Create job (+ optional schedule) |
| `GET` | `/api/admin/scrape/jobs/<id>` | Get job + schedules |
| `PATCH` | `/api/admin/scrape/jobs/<id>` | Update job fields |
| `POST` | `/api/admin/scrape/jobs/<id>/run` | Manually enqueue run (202) |
| `GET` | `/api/admin/scrape/jobs/<id>/runs` | List runs for job |
| `GET` | `/api/admin/scrape/jobs/<id>/schedule` | List schedules |
| `PUT` | `/api/admin/scrape/jobs/<id>/schedule` | Create or update schedule |

### Preserved existing endpoints (not modified)

| Method | Path |
|---|---|
| `POST` | `/api/admin/stores/sync` |
| `POST` | `/api/stores/<store_id>/categories/sync` |
| `POST` | `/api/categories/<category_id>/products/sync` |
| `GET` | `/api/scrape-runs` |
| `GET` | `/api/scrape-runs/<run_id>` |
| `GET` | `/api/scrape-status` |

---

## Deferred / out-of-scope for MVP

The following are NOT implemented in this wave:

- **Heartbeat / lease recovery** — stalled `running` runs are not automatically
  returned to `queued`.
- **Hard cancellation** — no endpoint exists yet to cancel an in-progress run.
- **Checkpoint / resume** — `checkpoint_in_json` / `checkpoint_out_json` columns
  exist in the DB but resume logic in runners is not implemented.
- **Per-source concurrency quotas** — `concurrency_key` column is present but
  not enforced.
- **Advanced retry orchestration** — `max_retries` / `retry_backoff_sec` are
  persisted but not yet acted on by the worker or scheduler.
- **Distributed leader election** — single-process scheduler only.
- **Broker-backed queue** — in-process SQLite/PostgreSQL queue only.

