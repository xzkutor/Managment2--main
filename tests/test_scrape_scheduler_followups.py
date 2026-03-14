"""Tests for scheduler follow-up decisions (RFC-008 addendum).

Covers:
  Decision 1 — timezone-aware cron computation
  Decision 2 — manual overlap enforcement (409 Conflict)
  Decision 3 — PostgreSQL claim path (SQLite fallback tested here)
  Decision 4 — retry orchestration (retryable metadata, backoff, max_retries)

Also verifies scrape history/admin compatibility is not broken.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pricewatch.db.models import RunStatus
from pricewatch.db.repositories import (
    claim_next_queued_run,
    complete_run,
    create_scrape_job,
    enqueue_run,
    list_retry_candidates,
)
from pricewatch.scrape.schedule import compute_next_run, validate_timezone
from pricewatch.scrape.contracts import RunnerContext, RunnerResult, BaseRunner
from pricewatch.scrape.registry import register_runner, list_runner_types
from pricewatch.services.scrape_history_service import ScrapeHistoryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _past(sec: int = 120) -> datetime:
    return _now() - timedelta(seconds=sec)


def _future(sec: int = 3600) -> datetime:
    return _now() + timedelta(seconds=sec)


def _make_job(session, *, max_retries=0, retry_backoff_sec=60,
              allow_overlap=False, next_run_at=None, enabled=True):
    return create_scrape_job(
        session,
        source_key="test_shop_followup",
        runner_type="_test_retryable_runner",
        params_json={"store_id": 1},
        enabled=enabled,
        allow_overlap=allow_overlap,
        max_retries=max_retries,
        retry_backoff_sec=retry_backoff_sec,
        next_run_at=next_run_at or _past(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Decision 1 — Timezone-aware cron computation
# ─────────────────────────────────────────────────────────────────────────────

class TestTimezoneAwareCron:
    def test_cron_utc_vs_kyiv_differ(self):
        """UTC and Europe/Kyiv give different next_run_at for the same cron."""
        base = datetime(2026, 3, 13, 11, 30, 0, tzinfo=timezone.utc)
        result_utc = compute_next_run("cron", from_dt=base, cron_expr="0 12 * * *", tz_name="UTC")
        result_kyiv = compute_next_run("cron", from_dt=base, cron_expr="0 12 * * *", tz_name="Europe/Kyiv")
        # Kyiv is UTC+2 in winter; noon Kyiv = 10:00 UTC, which is before base,
        # so next occurrence is next day noon Kyiv = next day 10:00 UTC
        # UTC noon is after base (11:30 UTC), so UTC result = 12:00 UTC same day
        assert result_utc != result_kyiv
        # Both results must be timezone-aware UTC
        assert result_utc.tzinfo is not None
        assert result_kyiv.tzinfo is not None

    def test_cron_result_is_utc(self):
        base = datetime(2026, 3, 13, 0, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run("cron", from_dt=base, cron_expr="0 10 * * *", tz_name="Europe/Kyiv")
        assert result.tzinfo == timezone.utc

    def test_invalid_timezone_raises(self):
        with pytest.raises(ValueError, match="Invalid timezone"):
            compute_next_run("cron", from_dt=_now(), cron_expr="0 12 * * *", tz_name="Mars/Olympus")

    def test_validate_timezone_valid(self):
        # Should not raise
        validate_timezone("UTC")
        validate_timezone("Europe/Kyiv")
        validate_timezone("America/New_York")

    def test_validate_timezone_invalid(self):
        with pytest.raises(ValueError, match="Invalid timezone"):
            validate_timezone("Not/A/Timezone")

    def test_interval_ignores_timezone(self):
        """Interval schedules must not be affected by tz_name."""
        base = datetime(2026, 3, 13, 12, 0, 0, tzinfo=timezone.utc)
        result_utc = compute_next_run("interval", from_dt=base, interval_sec=3600, tz_name="UTC")
        result_kyiv = compute_next_run("interval", from_dt=base, interval_sec=3600, tz_name="Europe/Kyiv")
        assert result_utc == result_kyiv

    def test_cron_invalid_tz_in_schedule_rejects_before_computation(self):
        """Timezone validation happens eagerly, before any cron parsing."""
        with pytest.raises(ValueError):
            compute_next_run("cron", from_dt=_now(), cron_expr="0 * * * *", tz_name="Invalid/Zone")


# ─────────────────────────────────────────────────────────────────────────────
# Decision 2 — Manual overlap enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestManualEnqueueOverlap:
    def _create_job(self, client, allow_overlap=False):
        resp = client.post("/api/admin/scrape/jobs", json={
            "source_key": "overlap_test_shop",
            "runner_type": "store_category_sync",
            "params_json": {"store_id": 1},
            "allow_overlap": allow_overlap,
        })
        assert resp.status_code == 201
        return resp.get_json()["job"]["id"]

    def test_manual_enqueue_succeeds_no_active_run(self, client):
        job_id = self._create_job(client, allow_overlap=False)
        resp = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert resp.status_code == 202

    def test_manual_enqueue_409_when_overlap_disabled_and_active(self, client):
        job_id = self._create_job(client, allow_overlap=False)
        # Create first run — should succeed
        resp1 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert resp1.status_code == 202
        # Second run — should be rejected
        resp2 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert resp2.status_code == 409
        data = resp2.get_json()
        assert "conflict" in data.get("error", "")

    def test_manual_enqueue_allowed_when_allow_overlap_true(self, client):
        job_id = self._create_job(client, allow_overlap=True)
        resp1 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert resp1.status_code == 202
        # Second concurrent enqueue also allowed
        resp2 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert resp2.status_code == 202

    def test_manual_enqueue_succeeds_after_run_completes(self, client, db_session_scope):
        job_id = self._create_job(client, allow_overlap=False)
        resp1 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert resp1.status_code == 202
        run_id = resp1.get_json()["run"]["id"]

        # Complete the run in DB
        with db_session_scope() as session:
            complete_run(session, run_id, status=RunStatus.SUCCESS)

        # Now enqueue should work again
        resp2 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert resp2.status_code == 202


# ─────────────────────────────────────────────────────────────────────────────
# Decision 3 — SQLite fallback claim (PostgreSQL tested separately if available)
# ─────────────────────────────────────────────────────────────────────────────

class TestClaimFallback:
    def test_claim_returns_oldest_queued(self, db_session_scope):
        with db_session_scope() as session:
            now = _now()
            r1 = enqueue_run(session, run_type="x", trigger_type="manual")
            r1.queued_at = now - timedelta(minutes=10)
            r2 = enqueue_run(session, run_type="x", trigger_type="manual")
            r2.queued_at = now - timedelta(minutes=5)
            session.flush()

            claimed = claim_next_queued_run(session, "worker-a")
            assert claimed is not None
            assert claimed.id == r1.id

    def test_claim_sets_running_status(self, db_session_scope):
        with db_session_scope() as session:
            enqueue_run(session, run_type="x")
            run = claim_next_queued_run(session, "worker-b")
            assert run.status == RunStatus.RUNNING
            assert run.worker_id == "worker-b"
            assert run.started_at is not None

    def test_claim_returns_none_when_empty(self, db_session_scope):
        with db_session_scope() as session:
            result = claim_next_queued_run(session, "worker-c")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Decision 4 — Retry orchestration
# ─────────────────────────────────────────────────────────────────────────────

class TestRetryMetadataPersistence:
    """Worker persists retryable flag; worker never creates retry runs."""

    def test_retryable_false_on_success(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.SUCCESS, retryable=False)
            from pricewatch.db.repositories import get_run
            r = get_run(session, run.id)
            assert r.retryable is False

    def test_retryable_persisted_on_failed(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            from pricewatch.db.repositories import get_run
            r = get_run(session, run.id)
            assert r.retryable is True
            assert r.status == RunStatus.FAILED

    def test_retryable_on_success_is_ignored(self, db_session_scope):
        """Setting retryable=True on a success run should store False (no retry needed)."""
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.SUCCESS, retryable=True)
            from pricewatch.db.repositories import get_run
            r = get_run(session, run.id)
            # complete_run only stores retryable=True when status==failed
            assert r.retryable is False

    def test_worker_does_not_create_retry_run(self, db_session_scope):
        """After a failed run, the queue must still have exactly 0 queued runs."""
        # Register a failing runner if not already registered
        if "_fail_retryable_runner" not in list_runner_types():
            class _FR(BaseRunner):
                runner_type = "_fail_retryable_runner"
                def run(self, ctx: RunnerContext) -> RunnerResult:
                    return RunnerResult(status="failed", retryable=True)
            register_runner(_FR)

        from pricewatch.scrape.worker import process_one
        with db_session_scope() as session:
            enqueue_run(session, run_type="_fail_retryable_runner")
            process_one(session)
            # No new queued runs must exist after worker completes
            remaining = (
                session.query(__import__(
                    "pricewatch.db.models", fromlist=["ScrapeRun"]
                ).ScrapeRun)
                .filter_by(status=RunStatus.QUEUED)
                .count()
            )
        assert remaining == 0


class TestRetryListCandidates:
    def test_failed_retryable_is_candidate(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            candidates = list_retry_candidates(session)
        assert any(c.id == run.id for c in candidates)

    def test_failed_non_retryable_not_candidate(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=False)
            candidates = list_retry_candidates(session)
        assert not any(c.id == run.id for c in candidates)

    def test_exhausted_run_not_candidate(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            # Simulate scheduler budget exhaustion (both flags set)
            from pricewatch.db.repositories import get_run
            r = get_run(session, run.id)
            r.retry_exhausted = True
            r.retry_processed = True
            session.flush()
            candidates = list_retry_candidates(session)
        assert not any(c.id == run.id for c in candidates)

    def test_already_retried_not_candidate(self, db_session_scope):
        """A run that already has a retry child is NOT returned as candidate."""
        with db_session_scope() as session:
            source = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, source.id, status=RunStatus.FAILED, retryable=True)
            # Create a retry child pointing to source
            child = enqueue_run(session, run_type="x", trigger_type="retry", attempt=2)
            child.retry_of_run_id = source.id
            session.flush()
            candidates = list_retry_candidates(session)
        assert not any(c.id == source.id for c in candidates)


class TestSchedulerRetryOrchestration:
    def test_retry_not_enqueued_before_backoff(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick
        backoff = 3600  # 1 hour
        with db_session_scope() as session:
            job = _make_job(session, max_retries=2, retry_backoff_sec=backoff)
            run = enqueue_run(session, job_id=job.id, run_type=job.runner_type)
            claim_next_queued_run(session, "w")
            # Finish just now — backoff not yet elapsed
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            # Tick with now == just after failure
            tick = run_tick(session, now=_now())

        assert len(tick.retries_enqueued) == 0

    def test_retry_enqueued_after_backoff(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick
        backoff = 60
        with db_session_scope() as session:
            job = _make_job(session, max_retries=2, retry_backoff_sec=backoff)
            run = enqueue_run(session, job_id=job.id, run_type=job.runner_type)
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            # Backfill finished_at so backoff has elapsed
            from pricewatch.db.repositories import get_run
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 10)
            session.flush()
            tick = run_tick(session, now=_now())

        assert len(tick.retries_enqueued) >= 1

    def test_retry_has_correct_trigger_type(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick
        backoff = 30
        with db_session_scope() as session:
            job = _make_job(session, max_retries=3, retry_backoff_sec=backoff)
            run = enqueue_run(session, job_id=job.id, run_type=job.runner_type)
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            from pricewatch.db.repositories import get_run
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            run_tick(session, now=_now())
            # Find the retry run
            from pricewatch.db.models import ScrapeRun
            retry = (
                session.query(ScrapeRun)
                .filter(ScrapeRun.retry_of_run_id == run.id)
                .first()
            )
        assert retry is not None
        assert retry.trigger_type == "retry"
        assert retry.attempt == 2

    def test_retry_stops_at_max_retries(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick
        backoff = 1
        with db_session_scope() as session:
            job = _make_job(session, max_retries=1, retry_backoff_sec=backoff)
            # attempt=2 exceeds max_retries=1
            run = enqueue_run(session, job_id=job.id, run_type=job.runner_type, attempt=2)
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            from pricewatch.db.repositories import get_run
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            tick = run_tick(session, now=_now())

        assert len(tick.retries_enqueued) == 0

    def test_non_retryable_failure_never_retried(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick
        backoff = 1
        with db_session_scope() as session:
            job = _make_job(session, max_retries=3, retry_backoff_sec=backoff)
            run = enqueue_run(session, job_id=job.id, run_type=job.runner_type)
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=False)
            from pricewatch.db.repositories import get_run
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            tick = run_tick(session, now=_now())

        assert len(tick.retries_enqueued) == 0

    def test_source_marked_exhausted_after_retry(self, db_session_scope):
        """When a retry child IS created (budget not exhausted), the source run
        must be marked retry_processed=True but retry_exhausted MUST remain False.
        retry_exhausted is only True when the budget is truly depleted.
        """
        from pricewatch.scrape.scheduler import run_tick
        from pricewatch.db.repositories import get_run
        backoff = 1
        with db_session_scope() as session:
            job = _make_job(session, max_retries=2, retry_backoff_sec=backoff)
            run = enqueue_run(session, job_id=job.id, run_type=job.runner_type)
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            run_tick(session, now=_now())
            r2 = get_run(session, run.id)

        # RFC-012 §5.4: retry_processed marks scheduler handled this; budget NOT exhausted
        assert r2.retry_processed is True
        assert r2.retry_exhausted is False  # budget still has retries left


# ─────────────────────────────────────────────────────────────────────────────
# Commit 7 — Compatibility: existing endpoints not broken
# ─────────────────────────────────────────────────────────────────────────────

class TestHistoryCompatibility:
    def test_scrape_runs_endpoint(self, client):
        resp = client.get("/api/scrape-runs")
        assert resp.status_code == 200
        assert "runs" in resp.get_json()

    def test_scrape_run_detail_endpoint(self, client, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            run_id = run.id

        resp = client.get(f"/api/scrape-runs/{run_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        # Endpoint wraps the run under a "run" key
        run_data = data.get("run", data)
        # All retry-state fields must be present (RFC-012 §5.4)
        assert "retryable" in run_data
        assert "retry_of_run_id" in run_data
        assert "retry_processed" in run_data
        assert "retry_exhausted" in run_data

    def test_scrape_status_endpoint(self, client):
        resp = client.get("/api/scrape-status")
        assert resp.status_code == 200

    def test_serialize_run_contains_retry_fields(self, db_session_scope):
        from pricewatch.web.serializers import serialize_run
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            run_dict = serialize_run(run)
        assert "retryable" in run_dict
        assert "retry_of_run_id" in run_dict
        assert "retry_processed" in run_dict
        assert "retry_exhausted" in run_dict

    def test_history_service_list_retry_candidates(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            svc = ScrapeHistoryService(session)
            candidates = svc.list_retry_candidates()
        assert isinstance(candidates, list)
        assert any(c.id == run.id for c in candidates)

    def test_legacy_finished_status_still_normalized(self):
        from pricewatch.services.scrape_history_service import _normalize_status
        assert _normalize_status("finished") == RunStatus.SUCCESS

    def test_new_retry_status_values_not_remapped(self):
        from pricewatch.services.scrape_history_service import _normalize_status
        assert _normalize_status("queued") == "queued"
        assert _normalize_status("running") == "running"
        assert _normalize_status("retry") == "retry"

