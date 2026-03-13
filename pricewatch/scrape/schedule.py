"""pricewatch.scrape.schedule — Schedule timing / next-run computation.

All interaction with the ``croniter`` library is encapsulated here.
The rest of the codebase MUST NOT import croniter directly.

Supports two schedule types:
  - "interval"  — fixed number of seconds between runs (epoch-based, UTC)
  - "cron"      — cron expression evaluated in ``tz_name`` timezone

Timezone semantics (Decision 1 — RFC-008 addendum):
  - Cron expressions are interpreted in the schedule's configured timezone.
  - ``next_run_at`` is always stored as UTC.
  - Invalid timezone names are rejected immediately with ``ValueError``.
  - Interval schedules are not affected by timezone — they are epoch-based.

Misfire policy (MVP):
  If a job is overdue, scheduler enqueues at most one run per tick and
  advances next_run_at once (no backlog explosion).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# croniter is a hard runtime dep — installed via requirements.txt / pip
try:
    from croniter import croniter  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "croniter is required for cron schedule support. "
        "Install it with: pip install croniter"
    ) from exc

ScheduleType = Literal["interval", "cron"]

# Sentinel — cached validated ZoneInfo objects
_TZ_CACHE: dict[str, ZoneInfo] = {}


def _resolve_tz(tz_name: str) -> ZoneInfo:
    """Return a ``ZoneInfo`` for *tz_name*.

    Raises:
        ValueError: if *tz_name* is not a valid IANA timezone identifier.
    """
    if tz_name in _TZ_CACHE:
        return _TZ_CACHE[tz_name]
    try:
        zi = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Invalid timezone name: {tz_name!r}. "
            "Use a valid IANA timezone identifier such as 'UTC' or 'Europe/Kyiv'."
        ) from exc
    _TZ_CACHE[tz_name] = zi
    return zi


def compute_next_run(
    schedule_type: ScheduleType,
    *,
    from_dt: datetime,
    cron_expr: str | None = None,
    interval_sec: int | None = None,
    tz_name: str = "UTC",
    jitter_sec: int = 0,
) -> datetime:
    """Return the next scheduled datetime (UTC, timezone-aware) after *from_dt*.

    Args:
        schedule_type: "interval" or "cron".
        from_dt:       Reference datetime.  If naive, treated as UTC.
        cron_expr:     Cron expression (required when type == "cron").
        interval_sec:  Interval in seconds (required when type == "interval").
        tz_name:       IANA timezone for cron evaluation (default "UTC").
                       Validated strictly — unknown names raise ``ValueError``.
                       Interval schedules ignore this argument.
        jitter_sec:    Maximum random jitter seconds added to result (0 = none).

    Returns:
        Timezone-aware UTC datetime of the next scheduled run.

    Raises:
        ValueError: for invalid schedule_type, missing required args, or bad tz_name.
    """
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=timezone.utc)

    if schedule_type == "interval":
        if interval_sec is None or interval_sec <= 0:
            raise ValueError("interval_sec must be a positive integer for interval schedules")
        base = from_dt + timedelta(seconds=interval_sec)

    elif schedule_type == "cron":
        if not cron_expr:
            raise ValueError("cron_expr is required for cron schedules")

        # Validate timezone strictly (Decision 1)
        tz = _resolve_tz(tz_name)

        # Convert reference time to the schedule timezone for cron evaluation
        from_local: datetime = from_dt.astimezone(tz)
        # croniter expects a naive datetime in the schedule's local time
        from_naive = from_local.replace(tzinfo=None)
        it = croniter(cron_expr, start_time=from_naive)
        next_naive: datetime = it.get_next(datetime)
        # Attach the schedule timezone, then convert back to UTC
        next_local = next_naive.replace(tzinfo=tz)
        base = next_local.astimezone(timezone.utc)

    else:
        raise ValueError(f"Unknown schedule_type: {schedule_type!r}")

    if jitter_sec > 0:
        base = base + timedelta(seconds=random.randint(0, jitter_sec))

    return base


def validate_timezone(tz_name: str) -> None:
    """Raise ``ValueError`` if *tz_name* is not a valid IANA timezone name.

    Call this in request-validation paths to surface bad timezone input
    before it reaches schedule computation.
    """
    _resolve_tz(tz_name)


def advance_next_run(
    schedule_type: ScheduleType,
    *,
    current_next_run_at: datetime,
    now: datetime,
    cron_expr: str | None = None,
    interval_sec: int | None = None,
    tz_name: str = "UTC",
    jitter_sec: int = 0,
    misfire_policy: str = "skip",
) -> datetime:
    """Compute the new next_run_at after a run has fired.

    Misfire policy "skip":
      Advance by exactly one step from *current_next_run_at*.
      If the result is still in the past, advance once more from *now*
      (prevents backlog explosion; at most one extra pass).
    """
    next_dt = compute_next_run(
        schedule_type,
        from_dt=current_next_run_at,
        cron_expr=cron_expr,
        interval_sec=interval_sec,
        tz_name=tz_name,
        jitter_sec=jitter_sec,
    )
    # If still in the past (overdue), advance once more from now
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if next_dt <= now:
        next_dt = compute_next_run(
            schedule_type,
            from_dt=now,
            cron_expr=cron_expr,
            interval_sec=interval_sec,
            tz_name=tz_name,
            jitter_sec=0,  # no jitter on catch-up
        )
    return next_dt

