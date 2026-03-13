"""Tests for the scrape scheduler MVP.

Covers:
- DB model persistence (ScrapeJob, ScrapeSchedule, ScrapeRun scheduler fields)
- Repository functions (due jobs, overlap check, enqueue, claim, complete)
- schedule.py computation helpers (interval, cron)
- scheduler.run_tick logic
- worker.process_one dispatch
- API control-plane endpoints
- ScrapeHistoryService compatibility
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pricewatch.db.models import RunStatus
from pricewatch.db.repositories import (
    create_scrape_job,
    create_scrape_schedule,
    list_scrape_jobs,
    list_due_scrape_jobs,
    has_active_run_for_job,
    enqueue_run,
    claim_next_queued_run,
    complete_run,
    list_runs_for_job,
    update_scrape_job,
)
from pricewatch.scrape.schedule import compute_next_run, advance_next_run
from pricewatch.scrape.contracts import BaseRunner, RunnerContext, RunnerResult
from pricewatch.scrape.registry import register_runner, list_runner_types
from pricewatch.services.scrape_history_service import ScrapeHistoryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _past(seconds: int = 60) -> datetime:
    return _utcnow() - timedelta(seconds=seconds)


def _future(seconds: int = 60) -> datetime:
    return _utcnow() + timedelta(seconds=seconds)


def _make_job(session, *, next_run_at=None, enabled=True, allow_overlap=False):
    return create_scrape_job(
        session,
        source_key="test_shop",
        runner_type="store_category_sync",
        params_json={"store_id": 1},
        enabled=enabled,
        allow_overlap=allow_overlap,
        next_run_at=next_run_at or _past(),
    )


# ---------------------------------------------------------------------------
# schedule.py — compute_next_run
# ---------------------------------------------------------------------------

class TestComputeNextRun:
    def test_interval_basic(self):
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run("interval", from_dt=base, interval_sec=3600)
        assert result == datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

    def test_interval_requires_positive(self):
        with pytest.raises(ValueError, match="positive"):
            compute_next_run("interval", from_dt=_utcnow(), interval_sec=0)

    def test_cron_basic(self):
        # "every hour at minute 0"
        base = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
        result = compute_next_run("cron", from_dt=base, cron_expr="0 * * * *")
        assert result.minute == 0
        assert result.hour == 13

    def test_cron_requires_expr(self):
        with pytest.raises(ValueError, match="cron_expr"):
            compute_next_run("cron", from_dt=_utcnow(), cron_expr=None)

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown schedule_type"):
            compute_next_run("weekly", from_dt=_utcnow())  # type: ignore[arg-type]

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime(2026, 1, 1, 0, 0, 0)  # no tzinfo
        result = compute_next_run("interval", from_dt=naive, interval_sec=60)
        assert result.tzinfo == timezone.utc

    def test_jitter_applied(self):
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        results = {
            compute_next_run("interval", from_dt=base, interval_sec=3600, jitter_sec=300)
            for _ in range(20)
        }
        # At least sometimes different from base+interval
        base_result = datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        lower = base_result
        upper = base_result + timedelta(seconds=300)
        for r in results:
            assert lower <= r <= upper


class TestAdvanceNextRun:
    def test_interval_not_overdue(self):
        current = _future(3600)
        now = _utcnow()
        result = advance_next_run(
            "interval",
            current_next_run_at=current,
            now=now,
            interval_sec=3600,
        )
        assert result > now

    def test_interval_overdue_advances_past_now(self):
        current = _past(7200)
        now = _utcnow()
        result = advance_next_run(
            "interval",
            current_next_run_at=current,
            now=now,
            interval_sec=3600,
        )
        # Result must be in the future
        assert result > now


# ---------------------------------------------------------------------------
# Repository — ScrapeJob
# ---------------------------------------------------------------------------

class TestScrapeJobRepository:
    def test_create_and_get(self, db_session_scope):
        with db_session_scope() as session:
            job = create_scrape_job(
                session,
                source_key="myshop",
                runner_type="store_category_sync",
                params_json={"store_id": 42},
                enabled=True,
            )
            job_id = job.id

        with db_session_scope() as session:
            from pricewatch.db.repositories import get_scrape_job
            loaded = get_scrape_job(session, job_id)
            assert loaded is not None
            assert loaded.source_key == "myshop"
            assert loaded.params_json == {"store_id": 42}

    def test_list_enabled_filter(self, db_session_scope):
        with db_session_scope() as session:
            create_scrape_job(session, source_key="a", runner_type="x", enabled=True)
            create_scrape_job(session, source_key="b", runner_type="x", enabled=False)
            jobs = list_scrape_jobs(session, enabled=True)
        enabled_keys = [j.source_key for j in jobs]
        assert "a" in enabled_keys
        assert "b" not in enabled_keys

    def test_list_due_jobs(self, db_session_scope):
        with db_session_scope() as session:
            due_job = create_scrape_job(
                session,
                source_key="due",
                runner_type="x",
                enabled=True,
                next_run_at=_past(120),
            )
            future_job = create_scrape_job(  # noqa: F841
                session,
                source_key="future",
                runner_type="x",
                enabled=True,
                next_run_at=_future(3600),
            )
            due = list_due_scrape_jobs(session, _utcnow())
        source_keys = [j.source_key for j in due]
        assert "due" in source_keys
        assert "future" not in source_keys

    def test_has_active_run_no_runs(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            result = has_active_run_for_job(session, job.id)
        assert result is False

    def test_has_active_run_with_queued(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            enqueue_run(session, job_id=job.id, run_type=job.runner_type)
            result = has_active_run_for_job(session, job.id)
        assert result is True

    def test_update_scrape_job(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            job_id = job.id
            update_scrape_job(session, job_id, enabled=False, priority=5)

        with db_session_scope() as session:
            from pricewatch.db.repositories import get_scrape_job
            j = get_scrape_job(session, job_id)
            assert j.enabled is False
            assert j.priority == 5


# ---------------------------------------------------------------------------
# Repository — ScrapeSchedule
# ---------------------------------------------------------------------------

class TestScrapeScheduleRepository:
    def test_create_and_get(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            sched = create_scrape_schedule(
                session,
                job_id=job.id,
                schedule_type="interval",
                interval_sec=3600,
            )
            sched_id = sched.id

        with db_session_scope() as session:
            from pricewatch.db.repositories import get_schedule_for_job
            loaded = get_schedule_for_job(session, job.id)
            assert loaded is not None
            assert loaded.interval_sec == 3600


# ---------------------------------------------------------------------------
# Repository — ScrapeRun queue lifecycle
# ---------------------------------------------------------------------------

class TestScrapeRunQueueLifecycle:
    def test_enqueue_creates_queued_run(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            run = enqueue_run(session, job_id=job.id, run_type="store_category_sync")
            assert run.status == RunStatus.QUEUED
            assert run.queued_at is not None

    def test_claim_transitions_to_running(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            enqueue_run(session, job_id=job.id, run_type="store_category_sync")
            run = claim_next_queued_run(session, "worker-1")
            assert run is not None
            assert run.status == RunStatus.RUNNING
            assert run.worker_id == "worker-1"

    def test_claim_returns_none_when_no_queued(self, db_session_scope):
        with db_session_scope() as session:
            result = claim_next_queued_run(session, "worker-x")
        assert result is None

    def test_complete_run_success(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            run = enqueue_run(session, job_id=job.id, run_type="store_category_sync")
            run_id = run.id
            claim_next_queued_run(session, "w1")
            complete_run(session, run_id, status=RunStatus.SUCCESS)

        with db_session_scope() as session:
            from pricewatch.db.repositories import get_run
            r = get_run(session, run_id)
            assert r.status == RunStatus.SUCCESS
            assert r.finished_at is not None

    def test_list_runs_for_job(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            for _ in range(3):
                enqueue_run(session, job_id=job.id, run_type="store_category_sync")
            runs = list_runs_for_job(session, job.id)
        assert len(runs) == 3


# ---------------------------------------------------------------------------
# Scheduler run_tick
# ---------------------------------------------------------------------------

class TestSchedulerTick:
    def test_due_job_gets_enqueued(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick

        with db_session_scope() as session:
            job = _make_job(session, next_run_at=_past(300))
            create_scrape_schedule(
                session, job_id=job.id, schedule_type="interval", interval_sec=3600
            )
            tick = run_tick(session, now=_utcnow())

        assert job.id not in tick.errors or len(tick.errors) == 0
        assert len(tick.enqueued) >= 1

    def test_disabled_job_not_due(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick

        with db_session_scope() as session:
            _make_job(session, next_run_at=_past(300), enabled=False)
            tick = run_tick(session, now=_utcnow())

        assert len(tick.enqueued) == 0

    def test_overlap_guard(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick

        with db_session_scope() as session:
            job = _make_job(session, next_run_at=_past(300), allow_overlap=False)
            create_scrape_schedule(
                session, job_id=job.id, schedule_type="interval", interval_sec=3600
            )
            # Simulate already-active run
            enqueue_run(session, job_id=job.id, run_type=job.runner_type)
            tick = run_tick(session, now=_utcnow())

        assert job.id in tick.skipped_overlap
        assert len(tick.enqueued) == 0

    def test_overdue_job_advances_next_run_at(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick

        with db_session_scope() as session:
            now = _utcnow()
            job = _make_job(session, next_run_at=now - timedelta(hours=3))
            create_scrape_schedule(
                session, job_id=job.id, schedule_type="interval", interval_sec=3600
            )
            run_tick(session, now=now)
            # After tick, next_run_at should be in the future
            assert job.next_run_at is not None
            assert job.next_run_at > now


# ---------------------------------------------------------------------------
# Worker — process_one dispatch
# ---------------------------------------------------------------------------

class _NullRunner(BaseRunner):
    """Test runner — always succeeds, does nothing."""
    runner_type = "_test_null_runner"

    def run(self, ctx: RunnerContext) -> RunnerResult:
        return RunnerResult(status="success", products_processed=7)


# Register test runner only once
if "_test_null_runner" not in list_runner_types():
    register_runner(_NullRunner)


class _FailRunner(BaseRunner):
    runner_type = "_test_fail_runner"

    def run(self, ctx: RunnerContext) -> RunnerResult:
        return RunnerResult(status="failed", error_message="deliberate failure")


if "_test_fail_runner" not in list_runner_types():
    register_runner(_FailRunner)


class TestWorkerProcessOne:
    def _enqueue(self, session, runner_type: str):
        return enqueue_run(session, run_type=runner_type, trigger_type="manual")

    def test_no_work_returns_unclaimed(self, db_session_scope):
        from pricewatch.scrape.worker import process_one
        with db_session_scope() as session:
            wr = process_one(session)
        assert wr.claimed is False

    def test_successful_run(self, db_session_scope):
        from pricewatch.scrape.worker import process_one
        with db_session_scope() as session:
            run = self._enqueue(session, "_test_null_runner")
            run_id = run.id
            wr = process_one(session)

        assert wr.claimed is True
        assert wr.run_id == run_id
        assert wr.outcome.status == "success"

        with db_session_scope() as session:
            from pricewatch.db.repositories import get_run
            r = get_run(session, run_id)
            assert r.status == "success"

    def test_failed_run_persisted(self, db_session_scope):
        from pricewatch.scrape.worker import process_one
        with db_session_scope() as session:
            run = self._enqueue(session, "_test_fail_runner")
            run_id = run.id
            wr = process_one(session)

        assert wr.outcome.status == "failed"
        with db_session_scope() as session:
            from pricewatch.db.repositories import get_run
            r = get_run(session, run_id)
            assert r.status == "failed"
            assert r.error_message == "deliberate failure"

    def test_unknown_runner_type_fails(self, db_session_scope):
        from pricewatch.scrape.worker import process_one
        with db_session_scope() as session:
            run = self._enqueue(session, "runner_does_not_exist")
            run_id = run.id
            wr = process_one(session)

        assert wr.claimed is True
        assert wr.error is not None
        with db_session_scope() as session:
            from pricewatch.db.repositories import get_run
            r = get_run(session, run_id)
            assert r.status == "failed"


# ---------------------------------------------------------------------------
# ScrapeHistoryService — compatibility
# ---------------------------------------------------------------------------

class TestScrapeHistoryService:
    def test_list_runs_empty(self, db_session_scope):
        with db_session_scope() as session:
            svc = ScrapeHistoryService(session)
            runs = svc.list_runs()
        assert isinstance(runs, list)

    def test_get_run_not_found_raises(self, db_session_scope):
        with db_session_scope() as session:
            svc = ScrapeHistoryService(session)
            with pytest.raises(ValueError, match="not found"):
                svc.get_run(999999)

    def test_legacy_status_finished_maps_to_success(self, db_session_scope):
        from pricewatch.services.scrape_history_service import _normalize_status
        assert _normalize_status("finished") == RunStatus.SUCCESS
        assert _normalize_status("running") == "running"
        assert _normalize_status(None) is None

    def test_list_runs_for_job(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            for _ in range(2):
                enqueue_run(session, job_id=job.id, run_type="store_category_sync")
            svc = ScrapeHistoryService(session)
            runs = svc.list_runs_for_job(job.id)
        assert len(runs) == 2


# ---------------------------------------------------------------------------
# API control-plane
# ---------------------------------------------------------------------------

class TestSchedulerAPIEndpoints:
    def _create_job_via_api(self, client, runner_type="store_category_sync"):
        return client.post(
            "/api/admin/scrape/jobs",
            json={
                "source_key": "test_shop",
                "runner_type": runner_type,
                "params_json": {"store_id": 1},
                "schedule": {
                    "schedule_type": "interval",
                    "interval_sec": 3600,
                },
            },
        )

    def test_create_job_returns_201(self, client):
        resp = self._create_job_via_api(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "job" in data
        assert data["job"]["runner_type"] == "store_category_sync"

    def test_list_jobs(self, client):
        self._create_job_via_api(client)
        resp = client.get("/api/admin/scrape/jobs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "jobs" in data
        assert len(data["jobs"]) >= 1

    def test_get_job(self, client):
        resp = self._create_job_via_api(client)
        job_id = resp.get_json()["job"]["id"]
        resp2 = client.get(f"/api/admin/scrape/jobs/{job_id}")
        assert resp2.status_code == 200
        assert resp2.get_json()["job"]["id"] == job_id

    def test_get_job_not_found(self, client):
        resp = client.get("/api/admin/scrape/jobs/99999")
        assert resp.status_code == 404

    def test_patch_job(self, client):
        resp = self._create_job_via_api(client)
        job_id = resp.get_json()["job"]["id"]
        resp2 = client.patch(
            f"/api/admin/scrape/jobs/{job_id}",
            json={"enabled": False, "priority": 10},
        )
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert data["job"]["enabled"] is False
        assert data["job"]["priority"] == 10

    def test_manual_enqueue_returns_202(self, client):
        resp = self._create_job_via_api(client)
        job_id = resp.get_json()["job"]["id"]
        resp2 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert resp2.status_code == 202
        data = resp2.get_json()
        assert "run" in data
        assert data["run"]["status"] == RunStatus.QUEUED

    def test_list_runs_for_job(self, client):
        resp = self._create_job_via_api(client)
        job_id = resp.get_json()["job"]["id"]
        # Enqueue a run
        client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        resp2 = client.get(f"/api/admin/scrape/jobs/{job_id}/runs")
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert len(data["runs"]) >= 1

    def test_create_job_missing_fields(self, client):
        resp = client.post(
            "/api/admin/scrape/jobs",
            json={"source_key": "only_key"},
        )
        assert resp.status_code == 400

    def test_existing_scrape_runs_endpoint_still_works(self, client):
        resp = client.get("/api/scrape-runs")
        assert resp.status_code == 200
        assert "runs" in resp.get_json()

    def test_scrape_status_endpoint_still_works(self, client):
        resp = client.get("/api/scrape-status")
        assert resp.status_code == 200

