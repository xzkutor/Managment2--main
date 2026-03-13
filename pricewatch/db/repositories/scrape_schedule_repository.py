"""pricewatch.db.repositories.scrape_schedule_repository

Persistence contract for ScrapeSchedule entities.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from pricewatch.db.models import ScrapeSchedule


def create_scrape_schedule(
    session: Session,
    *,
    job_id: int,
    schedule_type: str,
    cron_expr: str | None = None,
    interval_sec: int | None = None,
    timezone: str = "UTC",
    jitter_sec: int = 0,
    misfire_policy: str = "skip",
    enabled: bool = True,
) -> ScrapeSchedule:
    schedule = ScrapeSchedule(
        job_id=job_id,
        schedule_type=schedule_type,
        cron_expr=cron_expr,
        interval_sec=interval_sec,
        timezone=timezone,
        jitter_sec=jitter_sec,
        misfire_policy=misfire_policy,
        enabled=enabled,
    )
    session.add(schedule)
    session.flush()
    return schedule  # type: ignore[return-value]


def get_schedule_for_job(
    session: Session, job_id: int
) -> ScrapeSchedule | None:
    return (
        session.query(ScrapeSchedule)
        .filter(ScrapeSchedule.job_id == job_id, ScrapeSchedule.enabled == True)  # noqa: E712
        .first()
    )


def list_schedules_for_job(
    session: Session, job_id: int
) -> list[ScrapeSchedule]:
    rows = (
        session.query(ScrapeSchedule)
        .filter(ScrapeSchedule.job_id == job_id)
        .all()
    )
    return rows  # type: ignore[return-value]


def update_scrape_schedule(
    session: Session,
    schedule_id: int,
    *,
    cron_expr: str | None = None,
    interval_sec: int | None = None,
    timezone: str | None = None,
    jitter_sec: int | None = None,
    misfire_policy: str | None = None,
    enabled: bool | None = None,
) -> ScrapeSchedule:
    schedule = session.get(ScrapeSchedule, schedule_id)
    if not schedule:
        raise ValueError(f"ScrapeSchedule {schedule_id} not found")
    if cron_expr is not None:
        schedule.cron_expr = cron_expr
    if interval_sec is not None:
        schedule.interval_sec = interval_sec
    if timezone is not None:
        schedule.timezone = timezone
    if jitter_sec is not None:
        schedule.jitter_sec = jitter_sec
    if misfire_policy is not None:
        schedule.misfire_policy = misfire_policy
    if enabled is not None:
        schedule.enabled = enabled
    session.flush()
    return schedule  # type: ignore[return-value]


def delete_schedule_for_job(session: Session, job_id: int) -> int:
    """Delete all schedules for *job_id*. Returns number of deleted rows."""
    rows = (
        session.query(ScrapeSchedule)
        .filter(ScrapeSchedule.job_id == job_id)
        .all()
    )
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)

