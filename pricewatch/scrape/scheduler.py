"""pricewatch.scrape.scheduler — Due-job detection and run-enqueue loop.

The scheduler does NOT execute any scraping logic.
It only:
1. discovers enabled, due jobs from the DB,
2. enforces no-overlap,
3. creates queued ScrapeRun records,
4. advances each job's next_run_at,
5. detects retryable failed runs and enqueues retry runs after backoff (Decision 4).

Intended to be called once per scheduler tick from a background thread or
a CLI command.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from pricewatch.db.repositories import (
    enqueue_run,
    get_schedule_for_job,
    get_scrape_job,
    has_active_run_for_job,
    list_due_scrape_jobs,
    list_retry_candidates,
    set_job_next_run_at,
)
from pricewatch.scrape.schedule import advance_next_run

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SchedulerTick:
    """Result of a single scheduler tick."""

    def __init__(self) -> None:
        self.enqueued: list[int] = []          # run_ids created (scheduled + retry)
        self.retries_enqueued: list[int] = []  # subset of enqueued — retry runs only
        self.skipped_overlap: list[int] = []   # job_ids skipped due to overlap
        self.skipped_no_schedule: list[int] = []  # job_ids with no enabled schedule
        self.errors: list[dict[str, Any]] = []


def run_tick(session: Any, *, now: datetime | None = None, limit: int = 50) -> SchedulerTick:
    """Perform a single scheduler tick.

    Processes two categories of work per tick:
    1. **Due jobs** — jobs whose next_run_at <= now.
    2. **Retry candidates** — failed, retryable runs whose backoff has elapsed.

    Args:
        session:  SQLAlchemy Session (caller must commit on success).
        now:      Reference datetime (UTC).  Defaults to current UTC time.
        limit:    Maximum number of due jobs to process per tick.

    Returns:
        SchedulerTick with summary of actions taken.
    """
    if now is None:
        now = _utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    tick = SchedulerTick()

    # -----------------------------------------------------------------------
    # Phase 1 — scheduled job runs
    # -----------------------------------------------------------------------
    due_jobs = list_due_scrape_jobs(session, now, limit=limit)

    for job in due_jobs:
        try:
            if not job.allow_overlap and has_active_run_for_job(session, job.id):
                logger.info(
                    "scheduler: skipping job %s (overlap guard, active run exists)", job.id
                )
                tick.skipped_overlap.append(job.id)
                _advance_job_next_run(session, job, now)
                continue

            schedule = get_schedule_for_job(session, job.id)
            if schedule is None:
                logger.warning(
                    "scheduler: job %s has no enabled schedule — skipping", job.id
                )
                tick.skipped_no_schedule.append(job.id)
                continue

            run = enqueue_run(
                session,
                job_id=job.id,
                store_id=None,
                run_type=job.runner_type,
                trigger_type="scheduled",
                metadata_json={"source_key": job.source_key},
            )
            tick.enqueued.append(run.id)
            logger.info("scheduler: enqueued run %s for job %s", run.id, job.id)

            next_run_at = advance_next_run(
                schedule.schedule_type,  # type: ignore[arg-type]
                current_next_run_at=job.next_run_at or now,
                now=now,
                cron_expr=schedule.cron_expr,
                interval_sec=schedule.interval_sec,
                tz_name=schedule.timezone or "UTC",
                jitter_sec=schedule.jitter_sec or 0,
                misfire_policy=schedule.misfire_policy or "skip",
            )
            set_job_next_run_at(session, job.id, next_run_at, last_run_at=now)

        except Exception as exc:
            logger.exception("scheduler: error processing job %s: %s", job.id, exc)
            tick.errors.append({"job_id": job.id, "error": str(exc)})

    # -----------------------------------------------------------------------
    # Phase 2 — retry runs (Decision 4 — RFC-008 addendum)
    # Scheduler is the single owner of retry enqueue semantics.
    # Worker MUST NOT create retry runs.
    # -----------------------------------------------------------------------
    _process_retry_candidates(session, tick, now, limit=limit)

    return tick


def _process_retry_candidates(
    session: Any,
    tick: SchedulerTick,
    now: datetime,
    *,
    limit: int,
) -> None:
    """Detect retryable failed runs and enqueue retry runs after backoff elapsed.

    RFC-012 retry-state semantics (Commits 3, 4, 6):
      - ``retry_processed`` is set on the source run once the scheduler has
        evaluated it — regardless of whether a retry child was created.
        This prevents a second retry child from being created for the same source.
      - ``retry_exhausted`` is set **only** when the ``max_retries`` budget is
        truly exhausted (i.e. the source run has used up all allowed attempts).
        It no longer doubles as a "scheduler has handled this" signal.
      - ``retry_of_run_id`` on the retry child is the canonical lineage pointer
        (RFC-012 §5.3).  ``metadata_json`` may carry auxiliary info but is NOT
        the source of retry lineage truth.

    Attempt arithmetic (RFC-012 §5.5):
      - initial run: attempt=1
      - ``max_retries`` = additional retries beyond the initial attempt
      - retries are allowed while ``(source.attempt - 1) < job.max_retries``
        equivalently: ``source.attempt <= job.max_retries``
    """
    candidates = list_retry_candidates(session, limit=limit)

    for source_run in candidates:
        try:
            if source_run.job_id is None:
                # Legacy/manual runs (no job_id) are not retry-orchestrated
                # by the scheduler.  Mark as processed to keep the queue clean.
                source_run.retry_processed = True
                session.flush()
                continue

            job = get_scrape_job(session, source_run.job_id)
            if job is None or not job.enabled:
                source_run.retry_processed = True
                session.flush()
                continue

            # --- Commit 4: explicit attempt arithmetic ---
            # retries_used = attempts already consumed beyond the initial run
            # allow retry when retries_used < max_retries, i.e. attempt <= max_retries
            attempt = source_run.attempt or 1
            retries_used = attempt - 1  # 0 for initial run, 1 after first retry, …
            if retries_used >= job.max_retries:
                # Budget truly exhausted — set both flags
                source_run.retry_processed = True
                source_run.retry_exhausted = True
                session.flush()
                logger.info(
                    "scheduler: run %s exhausted max_retries=%d for job %s "
                    "(attempt=%d, retries_used=%d)",
                    source_run.id, job.max_retries, job.id, attempt, retries_used,
                )
                continue

            if source_run.finished_at is None:
                continue
            backoff_sec = job.retry_backoff_sec or 60
            retry_due_at = source_run.finished_at + timedelta(seconds=backoff_sec)
            if retry_due_at > now:
                continue

            if not job.allow_overlap and has_active_run_for_job(session, job.id):
                continue

            # --- Commit 6: retry_of_run_id is the canonical lineage pointer ---
            # metadata_json carries auxiliary info only; do NOT duplicate
            # retry_of_run_id there as a canonical source of truth.
            retry_run = enqueue_run(
                session,
                job_id=job.id,
                run_type=job.runner_type,
                trigger_type="retry",
                attempt=attempt + 1,
                metadata_json={"source_key": job.source_key},
                checkpoint_in_json=source_run.checkpoint_out_json,
            )
            retry_run.retry_of_run_id = source_run.id  # type: ignore[assignment]

            # --- Commit 3: mark source as processed (not exhausted) ---
            source_run.retry_processed = True
            session.flush()

            tick.enqueued.append(retry_run.id)
            tick.retries_enqueued.append(retry_run.id)
            logger.info(
                "scheduler: enqueued retry run %s (attempt=%d) for job %s "
                "(source %s, retries_used=%d/%d)",
                retry_run.id, attempt + 1, job.id,
                source_run.id, retries_used + 1, job.max_retries,
            )

        except Exception as exc:
            logger.exception(
                "scheduler: error processing retry candidate run %s: %s",
                source_run.id, exc,
            )
            tick.errors.append({"retry_of_run_id": source_run.id, "error": str(exc)})


def _advance_job_next_run(session: Any, job: Any, now: datetime) -> None:
    """Advance next_run_at for a job that was skipped due to overlap."""
    schedule = get_schedule_for_job(session, job.id)
    if schedule is None:
        return
    try:
        next_run_at = advance_next_run(
            schedule.schedule_type,  # type: ignore[arg-type]
            current_next_run_at=job.next_run_at or now,
            now=now,
            cron_expr=schedule.cron_expr,
            interval_sec=schedule.interval_sec,
            tz_name=schedule.timezone or "UTC",
            jitter_sec=0,
            misfire_policy="skip",
        )
        set_job_next_run_at(session, job.id, next_run_at)
    except Exception as exc:
        logger.warning(
            "scheduler: could not advance next_run_at for job %s: %s", job.id, exc
        )


def run_loop(
    session_factory: Callable[[], Any],
    *,
    tick_interval_sec: int = 30,
    max_ticks: int | None = None,
    on_tick_start: Callable[[], None] | None = None,
    on_tick_done: Callable[[SchedulerTick], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """Blocking scheduler loop — call ``run_tick`` on every interval.

    Args:
        session_factory:    Callable returning a new SQLAlchemy Session per tick.
        tick_interval_sec:  Seconds to sleep between ticks.
        max_ticks:          If set, stop after this many ticks (for testing).
        on_tick_start:      Optional callback invoked at the start of each tick.
        on_tick_done:       Optional callback invoked after a successful tick.
        on_error:           Optional callback invoked when a tick raises.

    Note: bootstrap module passes its own on_tick_start/on_tick_done/on_error
    callbacks to update process-local runtime status without coupling this
    module to bootstrap internals.
    """
    ticks = 0
    logger.info(
        "scheduler: run_loop started (tick_interval=%ds, max_ticks=%s)",
        tick_interval_sec, max_ticks,
    )
    while True:
        session = session_factory()
        try:
            if on_tick_start:
                on_tick_start()
            tick = run_tick(session)
            session.commit()
            if on_tick_done:
                on_tick_done(tick)
            if tick.enqueued:
                logger.info(
                    "scheduler: tick done — enqueued=%d (retries=%d), errors=%d",
                    len(tick.enqueued),
                    len(tick.retries_enqueued),
                    len(tick.errors),
                )
        except Exception as exc:
            logger.exception("scheduler: tick raised an error: %s", exc)
            try:
                session.rollback()
            except Exception:
                pass
            if on_error:
                on_error(exc)
        finally:
            try:
                session.close()
            except Exception:
                pass

        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            logger.info("scheduler: run_loop reached max_ticks=%d, stopping", max_ticks)
            break
        _time.sleep(tick_interval_sec)


