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
from datetime import datetime, timedelta, timezone
from typing import Any

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
    """Detect retryable failed runs and enqueue retry runs after backoff elapsed."""
    candidates = list_retry_candidates(session, limit=limit)

    for source_run in candidates:
        try:
            if source_run.job_id is None:
                continue

            job = get_scrape_job(session, source_run.job_id)
            if job is None or not job.enabled:
                continue

            attempt = source_run.attempt or 1
            if attempt > job.max_retries:
                source_run.retry_exhausted = True
                session.flush()
                logger.info(
                    "scheduler: run %s exhausted max_retries=%d for job %s",
                    source_run.id, job.max_retries, job.id,
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

            retry_run = enqueue_run(
                session,
                job_id=job.id,
                run_type=job.runner_type,
                trigger_type="retry",
                attempt=attempt + 1,
                metadata_json={
                    "source_key": job.source_key,
                    "retry_of_run_id": source_run.id,
                },
                checkpoint_in_json=source_run.checkpoint_out_json,
            )
            retry_run.retry_of_run_id = source_run.id  # type: ignore[assignment]
            source_run.retry_exhausted = True
            session.flush()

            tick.enqueued.append(retry_run.id)
            tick.retries_enqueued.append(retry_run.id)
            logger.info(
                "scheduler: enqueued retry run %s (attempt=%d) for job %s (source %s)",
                retry_run.id, attempt + 1, job.id, source_run.id,
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
