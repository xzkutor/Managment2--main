"""pricewatch.db.repositories.scrape_job_repository

Persistence contract for ScrapeJob and ScrapeSchedule entities.
All claim/scheduling logic stays in repositories; callers never need to
know which DB backend is in use.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from sqlalchemy.orm import Session

from pricewatch.db.models import ScrapeJob, ScrapeRun


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_scrape_job(
    session: Session,
    *,
    source_key: str,
    runner_type: str,
    params_json: dict | None = None,
    enabled: bool = True,
    priority: int = 0,
    allow_overlap: bool = False,
    timeout_sec: int | None = None,
    max_retries: int = 0,
    retry_backoff_sec: int = 60,
    concurrency_key: str | None = None,
    next_run_at: datetime | None = None,
) -> ScrapeJob:
    job = ScrapeJob(
        source_key=source_key,
        runner_type=runner_type,
        params_json=params_json,
        enabled=enabled,
        priority=priority,
        allow_overlap=allow_overlap,
        timeout_sec=timeout_sec,
        max_retries=max_retries,
        retry_backoff_sec=retry_backoff_sec,
        concurrency_key=concurrency_key,
        next_run_at=next_run_at,
    )
    session.add(job)
    session.flush()
    return cast(ScrapeJob, job)


def get_scrape_job(session: Session, job_id: int) -> ScrapeJob | None:
    return session.get(ScrapeJob, job_id)


def list_scrape_jobs(
    session: Session,
    *,
    enabled: bool | None = None,
    runner_type: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[ScrapeJob]:
    q = session.query(ScrapeJob).order_by(ScrapeJob.priority.desc(), ScrapeJob.id)
    if enabled is not None:
        q = q.filter(ScrapeJob.enabled == enabled)
    if runner_type is not None:
        q = q.filter(ScrapeJob.runner_type == runner_type)
    if limit is not None:
        q = q.limit(limit)
    if offset is not None:
        q = q.offset(offset)
    return cast(list[ScrapeJob], cast(object, q.all()))


def update_scrape_job(
    session: Session,
    job_id: int,
    *,
    enabled: bool | None = None,
    priority: int | None = None,
    allow_overlap: bool | None = None,
    timeout_sec: int | None = None,
    max_retries: int | None = None,
    retry_backoff_sec: int | None = None,
    concurrency_key: str | None = None,
    next_run_at: datetime | None = None,
    params_json: dict | None = None,
) -> ScrapeJob:
    job = session.get(ScrapeJob, job_id)
    if not job:
        raise ValueError(f"ScrapeJob {job_id} not found")
    if enabled is not None:
        job.enabled = enabled
    if priority is not None:
        job.priority = priority
    if allow_overlap is not None:
        job.allow_overlap = allow_overlap
    if timeout_sec is not None:
        job.timeout_sec = timeout_sec
    if max_retries is not None:
        job.max_retries = max_retries
    if retry_backoff_sec is not None:
        job.retry_backoff_sec = retry_backoff_sec
    if concurrency_key is not None:
        job.concurrency_key = concurrency_key
    if next_run_at is not None:
        job.next_run_at = next_run_at
    if params_json is not None:
        job.params_json = params_json
    session.flush()
    return job  # type: ignore[return-value]


def set_job_next_run_at(
    session: Session,
    job_id: int,
    next_run_at: datetime,
    *,
    last_run_at: datetime | None = None,
) -> ScrapeJob:
    job = session.get(ScrapeJob, job_id)
    if not job:
        raise ValueError(f"ScrapeJob {job_id} not found")
    job.next_run_at = next_run_at
    if last_run_at is not None:
        job.last_run_at = last_run_at
    session.flush()
    return job  # type: ignore[return-value]


def list_due_scrape_jobs(
    session: Session,
    now: datetime,
    *,
    limit: int = 50,
) -> list[ScrapeJob]:
    """Return enabled jobs whose next_run_at is <= now, ordered by priority desc."""
    q = (
        session.query(ScrapeJob)
        .filter(ScrapeJob.enabled == True)  # noqa: E712
        .filter(ScrapeJob.next_run_at <= now)
        .order_by(ScrapeJob.priority.desc(), ScrapeJob.next_run_at)
        .limit(limit)
    )
    return cast(list[ScrapeJob], cast(object, q.all()))


def has_active_run_for_job(session: Session, job_id: int) -> bool:
    """Return True when there is a queued or running ScrapeRun for this job."""
    count = (
        session.query(ScrapeRun)
        .filter(ScrapeRun.job_id == job_id)
        .filter(ScrapeRun.status.in_(["queued", "running"]))
        .count()
    )
    return count > 0

