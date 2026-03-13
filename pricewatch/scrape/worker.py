"""pricewatch.scrape.worker — Queued-run claiming and runner dispatch.

The worker:
1. claims the next queued ScrapeRun via the repository contract,
2. resolves the runner class from the scrape runner registry,
3. builds RunnerContext,
4. executes the runner (runner must NOT commit),
5. persists success/partial/failure outcome through repositories.

Intended to be called in a loop from a background thread or CLI command.
"""
from __future__ import annotations

import logging
import socket
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pricewatch.db.repositories import (
    claim_next_queued_run,
    complete_run,
    update_counters,
)
from pricewatch.scrape.contracts import RunnerContext, RunnerResult
from pricewatch.scrape.registry import get_runner

# Ensure runners are registered when this module is imported
import pricewatch.scrape.runners  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Process-local worker runtime state
# ---------------------------------------------------------------------------
_worker_lock = threading.Lock()
_worker_state: dict = {
    "running":                False,  # True while run_loop is executing in this process
    "started_at":             None,   # datetime | None — when run_loop first started
    "last_poll_at":           None,   # datetime | None
    "last_claimed_run_id":    None,   # int | None
    "last_completed_run_id":  None,   # int | None
    "last_error":             None,   # str | None
    "polls_total":            0,
    "runs_claimed_total":     0,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_worker_runtime_status() -> dict:
    """Return a snapshot of the aggregated worker runtime state.

    Safe to call from any thread.  All counters are process-local only
    (not persisted to DB).
    """
    with _worker_lock:
        return {
            "running":    _worker_state["running"],
            "started_at": (
                _worker_state["started_at"].isoformat()
                if _worker_state["started_at"] else None
            ),
            "worker_last_poll_at": (
                _worker_state["last_poll_at"].isoformat()
                if _worker_state["last_poll_at"] else None
            ),
            "worker_last_claimed_run_id":   _worker_state["last_claimed_run_id"],
            "worker_last_completed_run_id": _worker_state["last_completed_run_id"],
            "worker_last_error":            _worker_state["last_error"],
            "worker_polls_total":           _worker_state["polls_total"],
            "worker_runs_claimed_total":    _worker_state["runs_claimed_total"],
        }


def _default_worker_id() -> str:
    """Generate a unique worker identifier."""
    return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class WorkerResult:
    """Summary of a single worker process_one call."""

    def __init__(
        self,
        *,
        claimed: bool = False,
        run_id: int | None = None,
        runner_type: str | None = None,
        outcome: RunnerResult | None = None,
        error: str | None = None,
    ) -> None:
        self.claimed = claimed
        self.run_id = run_id
        self.runner_type = runner_type
        self.outcome = outcome
        self.error = error


def process_one(
    session: Any,
    *,
    worker_id: str | None = None,
) -> WorkerResult:
    """Claim and execute one queued run.

    Args:
        session:    SQLAlchemy Session.  Worker does NOT commit;
                    caller is responsible for commit/rollback.
        worker_id:  Identifier for this worker process.  Auto-generated if None.

    Returns:
        WorkerResult — always returned; check `.claimed` to see if any work was done.
    """
    if worker_id is None:
        worker_id = _default_worker_id()

    # Update process-local poll counter
    with _worker_lock:
        _worker_state["last_poll_at"] = _utcnow()
        _worker_state["polls_total"] += 1

    # 1. Claim the next queued run
    run = claim_next_queued_run(session, worker_id)
    if run is None:
        return WorkerResult(claimed=False)

    runner_type = run.run_type or ""
    logger.info("worker: claimed run %s (runner_type=%r, worker=%s)", run.id, runner_type, worker_id)

    # Update process-local claimed stats
    with _worker_lock:
        _worker_state["last_claimed_run_id"] = run.id
        _worker_state["runs_claimed_total"] += 1

    # 2. Resolve runner
    try:
        runner_cls = get_runner(runner_type)
    except KeyError as exc:
        error_msg = str(exc)
        logger.error("worker: unknown runner_type %r for run %s: %s", runner_type, run.id, error_msg)
        complete_run(session, run.id, status="failed", error_message=error_msg)
        with _worker_lock:
            _worker_state["last_error"] = error_msg
            _worker_state["last_completed_run_id"] = run.id
        return WorkerResult(claimed=True, run_id=run.id, runner_type=runner_type, error=error_msg)

    # 3. Build context
    ctx = RunnerContext(
        run_id=run.id,
        job_id=run.job_id,
        runner_type=runner_type,
        params=dict(run.job.params_json or {}) if run.job and run.job.params_json else {},
        checkpoint_in=run.checkpoint_in_json,
        session=session,
    )

    # 4. Execute runner
    try:
        runner = runner_cls()
        result: RunnerResult = runner.run(ctx)
    except Exception as exc:
        error_msg = f"Runner raised unhandled exception: {exc}"
        logger.exception("worker: run %s raised: %s", run.id, exc)
        result = RunnerResult(status="failed", error_message=error_msg)

    # 5. Persist outcome
    # Worker persists retryable flag but MUST NOT enqueue a retry run (Decision 4).
    complete_run(
        session,
        run.id,
        status=result.status,
        error_message=result.error_message,
        checkpoint_out_json=result.checkpoint_out,
        retryable=result.retryable,
    )

    # Persist counters if the runner reported any
    _persist_counters(session, run.id, result)

    # Update process-local completion stats
    with _worker_lock:
        _worker_state["last_completed_run_id"] = run.id
        if result.status == "failed" and result.error_message:
            _worker_state["last_error"] = result.error_message
        else:
            _worker_state["last_error"] = None

    log_fn = logger.warning if result.status == "failed" else logger.info
    log_fn(
        "worker: run %s finished with status=%r (products_processed=%d)",
        run.id,
        result.status,
        result.products_processed,
    )

    return WorkerResult(
        claimed=True,
        run_id=run.id,
        runner_type=runner_type,
        outcome=result,
    )


def _persist_counters(session: Any, run_id: int, result: RunnerResult) -> None:
    """Persist counters from RunnerResult back onto ScrapeRun."""
    has_counters = any(
        [
            result.categories_processed,
            result.products_processed,
            result.products_created,
            result.products_updated,
            result.price_changes_detected,
        ]
    )
    if not has_counters:
        return
    try:
        update_counters(
            session,
            run_id,
            categories_processed=result.categories_processed or None,
            products_processed=result.products_processed or None,
            products_created=result.products_created or None,
            products_updated=result.products_updated or None,
            price_changes_detected=result.price_changes_detected or None,
        )
    except Exception as exc:
        logger.warning("worker: failed to persist counters for run %s: %s", run_id, exc)


def run_loop(
    session_factory: Any,
    *,
    worker_id: str | None = None,
    idle_sleep_sec: float = 5.0,
    max_iterations: int | None = None,
) -> None:
    """Simple blocking worker loop.  Intended for background thread or CLI.

    Args:
        session_factory:  Callable returning a new SQLAlchemy Session.
        worker_id:        Optional worker identifier.
        idle_sleep_sec:   Seconds to sleep when no work is found.
        max_iterations:   If set, stop after this many iterations (for testing).
    """
    import time  # noqa: PLC0415

    if worker_id is None:
        worker_id = _default_worker_id()

    # Mark worker loop as running in process-local state
    with _worker_lock:
        _worker_state["running"]    = True
        _worker_state["started_at"] = _utcnow()

    iterations = 0
    logger.info("worker loop starting (worker_id=%s)", worker_id)

    while True:
        session = session_factory()
        try:
            wr = process_one(session, worker_id=worker_id)
            if wr.claimed:
                session.commit()
            else:
                session.rollback()
                time.sleep(idle_sleep_sec)
        except Exception as exc:
            logger.exception("worker loop: unhandled error: %s", exc)
            try:
                session.rollback()
            except Exception:
                pass
            time.sleep(idle_sleep_sec)
        finally:
            try:
                session.close()
            except Exception:
                pass

        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            logger.info("worker loop: reached max_iterations=%d, stopping", max_iterations)
            break

