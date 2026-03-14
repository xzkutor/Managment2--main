from __future__ import annotations

from datetime import datetime
from typing import Mapping, cast

from sqlalchemy.orm import Session

from pricewatch.db.models import RunStatus, ScrapeRun, utcnow


DEFAULT_STATUS_RUNNING = "running"
# RFC-012 §5.1: ``success`` is the canonical completed-success status.
# ``finished`` is retained as a compatibility constant for old callers/filters only.
DEFAULT_STATUS_FINISHED = RunStatus.SUCCESS   # was "finished" — see RunStatus.FINISHED
DEFAULT_STATUS_FAILED = "failed"


def start_run(
    session: Session,
    *,
    store_id: int | None,
    run_type: str | None = None,
    metadata_json: Mapping | None = None,
) -> ScrapeRun:
    run = ScrapeRun(
        store_id=store_id,
        run_type=run_type,
        status=DEFAULT_STATUS_RUNNING,
        started_at=utcnow(),
        metadata_json=dict(metadata_json) if metadata_json else None,
    )
    session.add(run)
    session.flush()
    if not isinstance(run, ScrapeRun):
        raise TypeError("Invalid ScrapeRun instance")
    return run


def finish_run(
    session: Session,
    run_id: int,
    *,
    status: str = DEFAULT_STATUS_FINISHED,
    error_message: str | None = None,
) -> ScrapeRun:
    run = session.get(ScrapeRun, run_id)
    if not run:
        raise ValueError(f"ScrapeRun {run_id} not found")
    run.status = status
    if error_message is not None:
        run.error_message = error_message
    run.finished_at = utcnow()
    session.flush()
    if not isinstance(run, ScrapeRun):
        raise TypeError("Invalid ScrapeRun instance")
    return run


def fail_run(session: Session, run_id: int, error_message: str) -> ScrapeRun:
    run = session.get(ScrapeRun, run_id)
    if not run:
        raise ValueError(f"ScrapeRun {run_id} not found")
    run.status = DEFAULT_STATUS_FAILED
    run.error_message = error_message
    run.finished_at = utcnow()
    session.flush()
    if not isinstance(run, ScrapeRun):
        raise TypeError("Invalid ScrapeRun instance")
    return run


def increment_counters(
    session: Session,
    run_id: int,
    *,
    categories_processed: int = 0,
    products_processed: int = 0,
    products_created: int = 0,
    products_updated: int = 0,
    price_changes_detected: int = 0,
) -> ScrapeRun:
    run = session.get(ScrapeRun, run_id)
    if not run:
        raise ValueError(f"ScrapeRun {run_id} not found")
    run.categories_processed += categories_processed
    run.products_processed += products_processed
    run.products_created += products_created
    run.products_updated += products_updated
    run.price_changes_detected += price_changes_detected
    session.flush()
    if not isinstance(run, ScrapeRun):
        raise TypeError("Invalid ScrapeRun instance")
    return run


def get_run(session: Session, run_id: int) -> ScrapeRun | None:
    return session.get(ScrapeRun, run_id)


def list_runs(
    session: Session,
    *,
    store_id: int | None = None,
    run_type: str | None = None,
    status: str | None = None,
    trigger_type: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[ScrapeRun]:
    q = session.query(ScrapeRun).order_by(ScrapeRun.started_at.desc())
    if store_id is not None:
        q = q.filter(ScrapeRun.store_id == store_id)
    if run_type is not None:
        q = q.filter(ScrapeRun.run_type == run_type)
    if status is not None:
        q = q.filter(ScrapeRun.status == status)
    if trigger_type is not None:
        q = q.filter(ScrapeRun.trigger_type == trigger_type)
    if limit is not None:
        q = q.limit(limit)
    if offset is not None:
        q = q.offset(offset)
    return cast(list[ScrapeRun], cast(object, q.all()))


def update_counters(
    session: Session,
    run_id: int,
    *,
    categories_processed: int | None = None,
    products_processed: int | None = None,
    products_created: int | None = None,
    products_updated: int | None = None,
    price_changes_detected: int | None = None,
    absolute: bool = False,
) -> ScrapeRun:
    run = session.get(ScrapeRun, run_id)
    if not run:
        raise ValueError(f"ScrapeRun {run_id} not found")

    def _apply(current: int, value: int | None) -> int:
        if value is None:
            return current
        if absolute:
            return value
        return current + value

    run.categories_processed = _apply(run.categories_processed, categories_processed)  # type: ignore[arg-type]
    run.products_processed = _apply(run.products_processed, products_processed)  # type: ignore[arg-type]
    run.products_created = _apply(run.products_created, products_created)  # type: ignore[arg-type]
    run.products_updated = _apply(run.products_updated, products_updated)  # type: ignore[arg-type]
    run.price_changes_detected = _apply(run.price_changes_detected, price_changes_detected)  # type: ignore[arg-type]
    session.flush()
    if not isinstance(run, ScrapeRun):
        raise TypeError("Invalid ScrapeRun instance")
    return run  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Scheduler queue / lifecycle helpers
# ---------------------------------------------------------------------------

def enqueue_run(
    session: Session,
    *,
    job_id: int | None = None,
    store_id: int | None = None,
    run_type: str | None = None,
    trigger_type: str = "manual",
    attempt: int = 1,
    metadata_json: Mapping | None = None,
    checkpoint_in_json: Mapping | None = None,
) -> ScrapeRun:
    """Create a ScrapeRun in *queued* state — does not start execution."""
    run = ScrapeRun(
        job_id=job_id,
        store_id=store_id,
        run_type=run_type,
        trigger_type=trigger_type,
        status=RunStatus.QUEUED,
        attempt=attempt,
        queued_at=utcnow(),
        metadata_json=dict(metadata_json) if metadata_json else None,
        checkpoint_in_json=dict(checkpoint_in_json) if checkpoint_in_json else None,
    )
    session.add(run)
    session.flush()
    return run  # type: ignore[return-value]


def claim_next_queued_run(
    session: Session,
    worker_id: str,
) -> ScrapeRun | None:
    """Atomically claim the oldest queued run and mark it as running.

    Backend strategy (Decision 3 — RFC-008 addendum):
      - PostgreSQL: uses ``FOR UPDATE SKIP LOCKED`` for race-free multi-worker claiming.
      - Other backends (SQLite, etc.): falls back to a simple first-match strategy.

    Callers MUST NOT branch on backend type. This function is the single
    owned claim contract and hides all backend differences.
    """
    dialect_name: str = session.get_bind().dialect.name  # type: ignore[union-attr]

    if dialect_name == "postgresql":
        # Atomic, race-free claim for multi-worker PostgreSQL deployments
        from sqlalchemy import text  # noqa: PLC0415
        result = session.execute(
            text(
                """
                SELECT id FROM scrape_runs
                WHERE status = 'queued'
                ORDER BY queued_at ASC NULLS LAST, id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
        )
        row = result.fetchone()
        if row is None:
            return None
        run = session.get(ScrapeRun, row[0])
    else:
        # SQLite / dev fallback — no row-level locking
        run = (
            session.query(ScrapeRun)
            .filter(ScrapeRun.status == RunStatus.QUEUED)
            .order_by(ScrapeRun.queued_at.asc().nullslast(), ScrapeRun.id)
            .first()
        )

    if run is None:
        return None
    run.status = RunStatus.RUNNING
    run.worker_id = worker_id
    run.started_at = utcnow()
    session.flush()
    return run  # type: ignore[return-value]


def mark_run_running(
    session: Session,
    run_id: int,
    worker_id: str,
) -> ScrapeRun:
    """Transition an already-claimed run to running (idempotent)."""
    run = session.get(ScrapeRun, run_id)
    if not run:
        raise ValueError(f"ScrapeRun {run_id} not found")
    run.status = RunStatus.RUNNING
    run.worker_id = worker_id
    if run.started_at is None:
        run.started_at = utcnow()
    session.flush()
    return run  # type: ignore[return-value]


def complete_run(
    session: Session,
    run_id: int,
    *,
    status: str = RunStatus.SUCCESS,
    error_message: str | None = None,
    checkpoint_out_json: Mapping | None = None,
    retryable: bool = False,
) -> ScrapeRun:
    """Mark a run as finished with a terminal status.

    Args:
        retryable: If True and status == "failed", the scheduler MAY create
                   a retry run later.  The worker persists this flag but
                   MUST NOT enqueue a retry itself (Decision 4).
    """
    run = session.get(ScrapeRun, run_id)
    if not run:
        raise ValueError(f"ScrapeRun {run_id} not found")
    run.status = status
    run.finished_at = utcnow()
    if error_message is not None:
        run.error_message = error_message
    if checkpoint_out_json is not None:
        run.checkpoint_out_json = dict(checkpoint_out_json)
    # Persist retry eligibility — only meaningful when status == "failed"
    run.retryable = retryable and (status == RunStatus.FAILED)
    session.flush()
    return run  # type: ignore[return-value]


def list_retry_candidates(
    session: Session,
    *,
    job_id: int | None = None,
    backoff_cutoff: datetime | None = None,
    limit: int = 50,
) -> list[ScrapeRun]:
    """Return failed, retryable runs that have not been processed or exhausted yet.

    RFC-012 Commit 3 — uses ``retry_processed`` as the primary "scheduler has
    already handled this source run" guard, and ``retry_exhausted`` as the
    "budget truly exhausted" guard.  Both must be False for a run to be
    considered a candidate.

    A run is a retry candidate when:
      - status == "failed"
      - retryable == True
      - retry_processed == False  (scheduler has not evaluated this run yet)
      - retry_exhausted == False  (budget not explicitly exhausted)
      - no child run with retry_of_run_id pointing to this run exists
        (extra safety net via subquery)
      - if backoff_cutoff provided: finished_at <= backoff_cutoff

    Callers (scheduler) are responsible for:
      - checking max_retries via the job
      - marking source runs as retry_processed after handling
      - marking source runs as retry_exhausted when budget runs out
    """
    from sqlalchemy import select  # noqa: PLC0415
    from pricewatch.db.models import ScrapeRun as SR  # noqa: PLC0415

    # Safety net: runs that already have a retry child
    already_retried = (
        select(SR.retry_of_run_id)
        .where(SR.retry_of_run_id.isnot(None))
        .scalar_subquery()
    )

    q = (
        session.query(ScrapeRun)
        .filter(ScrapeRun.status == RunStatus.FAILED)
        .filter(ScrapeRun.retryable == True)        # noqa: E712
        .filter(ScrapeRun.retry_processed == False)  # noqa: E712  primary guard
        .filter(ScrapeRun.retry_exhausted == False)  # noqa: E712  budget guard
        .filter(~ScrapeRun.id.in_(already_retried))  # extra safety
    )
    if job_id is not None:
        q = q.filter(ScrapeRun.job_id == job_id)
    if backoff_cutoff is not None:
        q = q.filter(ScrapeRun.finished_at <= backoff_cutoff)
    q = q.order_by(ScrapeRun.finished_at.asc().nullslast()).limit(limit)
    return cast(list[ScrapeRun], cast(object, q.all()))


def list_runs_for_job(
    session: Session,
    job_id: int,
    *,
    status: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[ScrapeRun]:
    q = (
        session.query(ScrapeRun)
        .filter(ScrapeRun.job_id == job_id)
        .order_by(ScrapeRun.queued_at.desc().nullslast(), ScrapeRun.id.desc())
    )
    if status is not None:
        q = q.filter(ScrapeRun.status == status)
    if limit is not None:
        q = q.limit(limit)
    if offset is not None:
        q = q.offset(offset)
    return cast(list[ScrapeRun], cast(object, q.all()))


def get_queue_stats(session: Session) -> dict:
    """Return aggregated queue stats for operator visibility.

    Returns a dict with:
      - ``queued``          — number of runs currently in QUEUED status
      - ``running``         — number of runs currently in RUNNING status
      - ``failed_retryable``— failed runs that are retryable and not exhausted

    Suitable for inclusion in the ``/api/scrape-status`` response without
    leaking raw SQL into the route layer.
    """
    from sqlalchemy import func  # noqa: PLC0415

    queued = (
        session.query(func.count(ScrapeRun.id))
        .filter(ScrapeRun.status == RunStatus.QUEUED)
        .scalar() or 0
    )
    running = (
        session.query(func.count(ScrapeRun.id))
        .filter(ScrapeRun.status == RunStatus.RUNNING)
        .scalar() or 0
    )
    failed_retryable = (
        session.query(func.count(ScrapeRun.id))
        .filter(ScrapeRun.status == RunStatus.FAILED)
        .filter(ScrapeRun.retryable == True)    # noqa: E712
        .filter(ScrapeRun.retry_exhausted == False)  # noqa: E712
        .scalar() or 0
    )
    return {
        "queued":           int(queued),
        "running":          int(running),
        "failed_retryable": int(failed_retryable),
    }
