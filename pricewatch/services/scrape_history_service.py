from __future__ import annotations

from datetime import datetime

from pricewatch.db.models import RunStatus
from pricewatch.db.repositories import (
    list_runs,
    get_run,
    list_runs_for_job,
    list_scrape_jobs,
    get_scrape_job,
    list_retry_candidates,
)

# ---------------------------------------------------------------------------
# Legacy status compatibility map
# "finished" was used before the scheduler lifecycle was introduced.
# Callers may pass either the old or new value; both are accepted.
# ---------------------------------------------------------------------------
_LEGACY_STATUS_MAP: dict[str, str] = {
    "finished": RunStatus.SUCCESS,
}


def _normalize_status(status: str | None) -> str | None:
    """Map legacy status strings to current ones."""
    if status is None:
        return None
    return _LEGACY_STATUS_MAP.get(status, status)


class ScrapeHistoryService:
    def __init__(self, session):
        self.session = session

    # ------------------------------------------------------------------
    # Run history
    # ------------------------------------------------------------------

    def list_runs(
        self,
        *,
        store_id: int | None = None,
        run_type: str | None = None,
        status: str | None = None,
        trigger_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ):
        return list_runs(
            self.session,
            store_id=store_id,
            run_type=run_type,
            status=_normalize_status(status),
            trigger_type=trigger_type,
            limit=limit,
            offset=offset,
        )

    def get_run(self, run_id: int):
        run = get_run(self.session, run_id)
        if not run:
            raise ValueError(f"ScrapeRun {run_id} not found")
        return run

    def list_runs_for_job(
        self,
        job_id: int,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ):
        return list_runs_for_job(
            self.session,
            job_id,
            status=_normalize_status(status),
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Retry observability (read-only)
    # ------------------------------------------------------------------

    def list_retry_candidates(
        self,
        *,
        job_id: int | None = None,
        backoff_cutoff: datetime | None = None,
        limit: int = 50,
    ):
        """Return failed, retryable runs that have not been retried yet.

        This is a read-only view — enqueueing is done exclusively by the scheduler.
        """
        return list_retry_candidates(
            self.session,
            job_id=job_id,
            backoff_cutoff=backoff_cutoff,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Job listing (read-only convenience methods)
    # ------------------------------------------------------------------

    def list_jobs(
        self,
        *,
        enabled: bool | None = None,
        runner_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ):
        return list_scrape_jobs(
            self.session,
            enabled=enabled,
            runner_type=runner_type,
            limit=limit,
            offset=offset,
        )

    def get_job(self, job_id: int):
        job = get_scrape_job(self.session, job_id)
        if not job:
            raise ValueError(f"ScrapeJob {job_id} not found")
        return job


