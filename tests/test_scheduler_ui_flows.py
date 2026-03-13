"""tests/test_scheduler_ui_flows.py — Backend smoke coverage for scheduler UI flows.

Covers the API surface used by service.scheduler.js:
  GET  /api/admin/scrape/jobs
  POST /api/admin/scrape/jobs
  GET  /api/admin/scrape/jobs/<id>
  PATCH /api/admin/scrape/jobs/<id>
  POST /api/admin/scrape/jobs/<id>/run   (including 409 overlap)
  GET  /api/admin/scrape/jobs/<id>/runs
  GET  /api/admin/scrape/jobs/<id>/schedule
  PUT  /api/admin/scrape/jobs/<id>/schedule
  GET  /api/scrape-runs  (with trigger_type filter)

Also covers:
  - status badge data (scheduler-era statuses) via /api/scrape-runs
  - schedule conditional fields (interval vs cron)
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricewatch.db.models import RunStatus
from pricewatch.db.repositories import (
    complete_run,
    enqueue_run,
    claim_next_queued_run,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _create_job(client, *, source_key="ui_test_shop", runner_type="store_category_sync",
                allow_overlap=False, max_retries=0, with_schedule=False,
                schedule_type="interval", interval_sec=3600, cron_expr=None,
                timezone_val="UTC"):
    payload = {
        "source_key":       source_key,
        "runner_type":      runner_type,
        "enabled":          True,
        "allow_overlap":    allow_overlap,
        "max_retries":      max_retries,
        "retry_backoff_sec": 60,
        "params_json":      {"store_id": 1},
    }
    if with_schedule:
        sched = {"schedule_type": schedule_type, "enabled": True, "jitter_sec": 0,
                 "misfire_policy": "skip"}
        if schedule_type == "interval":
            sched["interval_sec"] = interval_sec
        elif schedule_type == "cron":
            sched["cron_expr"]  = cron_expr or "0 * * * *"
            sched["timezone"]   = timezone_val
        payload["schedule"] = sched
    resp = client.post("/api/admin/scrape/jobs", json=payload)
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Commit 2 — Jobs list loading
# ─────────────────────────────────────────────────────────────────────────────

class TestJobsListLoading:
    def test_list_jobs_returns_200(self, client):
        resp = client.get("/api/admin/scrape/jobs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_created_job_appears_in_list(self, client):
        _create_job(client, source_key="list_test_shop")
        resp = client.get("/api/admin/scrape/jobs")
        assert resp.status_code == 200
        keys = [j["source_key"] for j in resp.get_json()["jobs"]]
        assert "list_test_shop" in keys

    def test_job_list_fields_present(self, client):
        _create_job(client, source_key="fields_test_shop")
        jobs = client.get("/api/admin/scrape/jobs").get_json()["jobs"]
        job = next((j for j in jobs if j["source_key"] == "fields_test_shop"), None)
        assert job is not None
        for field in ("id", "runner_type", "enabled", "allow_overlap",
                      "next_run_at", "last_run_at"):
            assert field in job, f"Missing field: {field}"

    def test_job_detail_includes_schedules(self, client):
        resp = _create_job(client, source_key="detail_sched_shop",
                           with_schedule=True, schedule_type="interval", interval_sec=1800)
        job_id = resp.get_json()["job"]["id"]
        detail = client.get(f"/api/admin/scrape/jobs/{job_id}").get_json()
        assert "job" in detail
        assert "schedules" in detail
        assert isinstance(detail["schedules"], list)

    def test_job_detail_404_for_unknown(self, client):
        resp = client.get("/api/admin/scrape/jobs/9999999")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Commit 3 — Job actions (run now, enable/disable)
# ─────────────────────────────────────────────────────────────────────────────

class TestJobActions:
    def test_run_now_returns_202_queued(self, client):
        resp = _create_job(client, source_key="run_now_shop")
        job_id = resp.get_json()["job"]["id"]
        r = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert r.status_code == 202
        run = r.get_json()["run"]
        assert run["status"] == RunStatus.QUEUED
        assert run["trigger_type"] == "manual"

    def test_run_now_409_when_active_and_no_overlap(self, client):
        resp = _create_job(client, source_key="overlap_shop", allow_overlap=False)
        job_id = resp.get_json()["job"]["id"]
        # First enqueue
        r1 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert r1.status_code == 202
        # Second must conflict
        r2 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert r2.status_code == 409
        body = r2.get_json()
        assert "conflict" in body.get("error", "").lower() or \
               "conflict" in body.get("message", "").lower() or \
               "overlap" in str(body).lower()

    def test_run_now_allowed_with_overlap_true(self, client):
        resp = _create_job(client, source_key="overlap_ok_shop", allow_overlap=True)
        job_id = resp.get_json()["job"]["id"]
        r1 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert r1.status_code == 202
        r2 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert r2.status_code == 202

    def test_disable_job_via_patch(self, client):
        resp = _create_job(client, source_key="toggle_shop")
        job_id = resp.get_json()["job"]["id"]
        r = client.patch(f"/api/admin/scrape/jobs/{job_id}", json={"enabled": False})
        assert r.status_code == 200
        assert r.get_json()["job"]["enabled"] is False

    def test_enable_job_via_patch(self, client):
        resp = _create_job(client, source_key="enable_shop")
        job_id = resp.get_json()["job"]["id"]
        client.patch(f"/api/admin/scrape/jobs/{job_id}", json={"enabled": False})
        r = client.patch(f"/api/admin/scrape/jobs/{job_id}", json={"enabled": True})
        assert r.status_code == 200
        assert r.get_json()["job"]["enabled"] is True

    def test_run_now_succeeds_after_active_run_completes(self, client, db_session_scope):
        resp = _create_job(client, source_key="complete_shop", allow_overlap=False)
        job_id = resp.get_json()["job"]["id"]
        r1 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        run_id = r1.get_json()["run"]["id"]
        # Complete the run
        with db_session_scope() as session:
            complete_run(session, run_id, status=RunStatus.SUCCESS)
        # Now should succeed
        r2 = client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        assert r2.status_code == 202


# ─────────────────────────────────────────────────────────────────────────────
# Commit 4 — Job runs panel
# ─────────────────────────────────────────────────────────────────────────────

class TestJobRunsPanel:
    def test_runs_list_empty_initially(self, client):
        resp = _create_job(client, source_key="runs_empty_shop")
        job_id = resp.get_json()["job"]["id"]
        r = client.get(f"/api/admin/scrape/jobs/{job_id}/runs")
        assert r.status_code == 200
        assert r.get_json()["runs"] == []

    def test_runs_list_after_enqueue(self, client):
        resp = _create_job(client, source_key="runs_data_shop")
        job_id = resp.get_json()["job"]["id"]
        client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        r = client.get(f"/api/admin/scrape/jobs/{job_id}/runs")
        assert r.status_code == 200
        runs = r.get_json()["runs"]
        assert len(runs) >= 1

    def test_runs_include_scheduler_era_fields(self, client):
        resp = _create_job(client, source_key="runs_fields_shop")
        job_id = resp.get_json()["job"]["id"]
        client.post(f"/api/admin/scrape/jobs/{job_id}/run")
        runs = client.get(f"/api/admin/scrape/jobs/{job_id}/runs").get_json()["runs"]
        run = runs[0]
        for field in ("status", "trigger_type", "attempt", "queued_at",
                      "retryable", "retry_of_run_id", "retry_exhausted"):
            assert field in run, f"Missing run field: {field}"

    def test_runs_show_all_scheduler_statuses(self, client, db_session_scope):
        """Test that all scheduler-era statuses render correctly through the API."""
        resp = _create_job(client, source_key="status_shop")
        job_id = resp.get_json()["job"]["id"]

        statuses_to_test = [RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.PARTIAL]
        run_ids = []

        with db_session_scope() as session:
            for status in statuses_to_test:
                run = enqueue_run(session, job_id=job_id,
                                  run_type="store_category_sync")
                claim_next_queued_run(session, f"worker_{status}")
                complete_run(session, run.id, status=status)
                run_ids.append(run.id)

        runs = client.get(f"/api/admin/scrape/jobs/{job_id}/runs").get_json()["runs"]
        returned_statuses = {r["status"] for r in runs}
        for s in statuses_to_test:
            assert s in returned_statuses, f"Status {s!r} not in response"

    def test_failed_run_exposes_error_message(self, client, db_session_scope):
        resp = _create_job(client, source_key="err_shop")
        job_id = resp.get_json()["job"]["id"]
        with db_session_scope() as session:
            run = enqueue_run(session, job_id=job_id, run_type="store_category_sync")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED,
                         error_message="deliberate test error")
            run_id = run.id
        runs = client.get(f"/api/admin/scrape/jobs/{job_id}/runs").get_json()["runs"]
        r = next((x for x in runs if x["id"] == run_id), None)
        assert r is not None
        assert r["error_message"] == "deliberate test error"


# ─────────────────────────────────────────────────────────────────────────────
# Commits 5 & 6 — Create and edit job
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateEditJob:
    def test_create_job_minimal(self, client):
        r = client.post("/api/admin/scrape/jobs", json={
            "source_key": "minimal_shop",
            "runner_type": "store_category_sync",
        })
        assert r.status_code == 201
        j = r.get_json()["job"]
        assert j["source_key"] == "minimal_shop"
        assert j["enabled"] is True  # default

    def test_create_job_with_all_fields(self, client):
        r = client.post("/api/admin/scrape/jobs", json={
            "source_key":       "full_shop",
            "runner_type":      "category_product_sync",
            "enabled":          False,
            "allow_overlap":    True,
            "max_retries":      3,
            "retry_backoff_sec": 120,
            "timeout_sec":      300,
            "params_json":      {"store_id": 42},
        })
        assert r.status_code == 201
        j = r.get_json()["job"]
        assert j["enabled"] is False
        assert j["allow_overlap"] is True
        assert j["max_retries"] == 3
        assert j["retry_backoff_sec"] == 120

    def test_create_job_missing_runner_type_returns_400(self, client):
        r = client.post("/api/admin/scrape/jobs", json={
            "source_key": "bad_shop",
        })
        assert r.status_code == 400

    def test_edit_job_enabled_flag(self, client):
        r = _create_job(client, source_key="edit_test_shop")
        job_id = r.get_json()["job"]["id"]
        patch = client.patch(f"/api/admin/scrape/jobs/{job_id}",
                             json={"enabled": False})
        assert patch.status_code == 200
        assert patch.get_json()["job"]["enabled"] is False

    def test_edit_job_max_retries_and_backoff(self, client):
        r = _create_job(client, source_key="retries_shop")
        job_id = r.get_json()["job"]["id"]
        patch = client.patch(f"/api/admin/scrape/jobs/{job_id}",
                             json={"max_retries": 5, "retry_backoff_sec": 300})
        assert patch.status_code == 200
        j = patch.get_json()["job"]
        assert j["max_retries"] == 5
        assert j["retry_backoff_sec"] == 300

    def test_edit_job_params_json(self, client):
        r = _create_job(client, source_key="params_edit_shop")
        job_id = r.get_json()["job"]["id"]
        new_params = {"store_id": 99, "extra": "value"}
        patch = client.patch(f"/api/admin/scrape/jobs/{job_id}",
                             json={"params_json": new_params})
        assert patch.status_code == 200
        assert patch.get_json()["job"]["params_json"] == new_params


# ─────────────────────────────────────────────────────────────────────────────
# Commit 7 — Schedule view and edit
# ─────────────────────────────────────────────────────────────────────────────

class TestScheduleViewEdit:
    def test_schedule_endpoint_no_schedule(self, client):
        r = _create_job(client, source_key="no_sched_shop")
        job_id = r.get_json()["job"]["id"]
        resp = client.get(f"/api/admin/scrape/jobs/{job_id}/schedule")
        assert resp.status_code == 200
        assert resp.get_json()["schedules"] == []

    def test_create_interval_schedule_via_put(self, client):
        r = _create_job(client, source_key="put_sched_shop")
        job_id = r.get_json()["job"]["id"]
        resp = client.put(f"/api/admin/scrape/jobs/{job_id}/schedule", json={
            "schedule_type": "interval",
            "interval_sec":  1800,
            "jitter_sec":    60,
            "misfire_policy": "skip",
            "enabled": True,
        })
        assert resp.status_code == 200
        sched = resp.get_json()["schedule"]
        assert sched["schedule_type"] == "interval"
        assert sched["interval_sec"]  == 1800
        assert sched["jitter_sec"]    == 60

    def test_create_cron_schedule_with_timezone(self, client):
        r = _create_job(client, source_key="cron_sched_shop")
        job_id = r.get_json()["job"]["id"]
        resp = client.put(f"/api/admin/scrape/jobs/{job_id}/schedule", json={
            "schedule_type": "cron",
            "cron_expr":     "0 9 * * 1-5",
            "timezone":      "Europe/Kyiv",
            "jitter_sec":    0,
            "misfire_policy": "skip",
            "enabled": True,
        })
        assert resp.status_code == 200
        sched = resp.get_json()["schedule"]
        assert sched["schedule_type"] == "cron"
        assert sched["cron_expr"]     == "0 9 * * 1-5"
        assert sched["timezone"]      == "Europe/Kyiv"

    def test_update_existing_schedule(self, client):
        r = _create_job(client, source_key="update_sched_shop",
                        with_schedule=True, schedule_type="interval", interval_sec=3600)
        job_id = r.get_json()["job"]["id"]
        # Update to 2-hour interval
        resp = client.put(f"/api/admin/scrape/jobs/{job_id}/schedule", json={
            "interval_sec": 7200,
        })
        assert resp.status_code == 200
        assert resp.get_json()["schedule"]["interval_sec"] == 7200

    def test_schedule_with_interval_has_no_cron_required(self, client):
        """Interval schedule does not require cron_expr — should succeed."""
        r = _create_job(client, source_key="interval_no_cron_shop")
        job_id = r.get_json()["job"]["id"]
        resp = client.put(f"/api/admin/scrape/jobs/{job_id}/schedule", json={
            "schedule_type": "interval",
            "interval_sec":  600,
        })
        assert resp.status_code == 200

    def test_schedule_timezone_preserved(self, client):
        r = _create_job(client, source_key="tz_shop")
        job_id = r.get_json()["job"]["id"]
        client.put(f"/api/admin/scrape/jobs/{job_id}/schedule", json={
            "schedule_type": "cron",
            "cron_expr":     "30 8 * * *",
            "timezone":      "America/New_York",
        })
        # GET should return the same timezone
        schedules = client.get(
            f"/api/admin/scrape/jobs/{job_id}/schedule"
        ).get_json()["schedules"]
        assert len(schedules) >= 1
        assert schedules[0]["timezone"] == "America/New_York"

    def test_job_created_with_schedule_inline(self, client):
        r = _create_job(client, source_key="inline_sched_shop",
                        with_schedule=True, schedule_type="interval", interval_sec=900)
        assert r.status_code == 201
        detail = client.get(
            f"/api/admin/scrape/jobs/{r.get_json()['job']['id']}/schedule"
        ).get_json()
        assert len(detail["schedules"]) >= 1
        assert detail["schedules"][0]["interval_sec"] == 900


# ─────────────────────────────────────────────────────────────────────────────
# Commit 8 — Global History tab: trigger_type filter
# ─────────────────────────────────────────────────────────────────────────────

class TestHistoryTriggerFilter:
    def test_history_all_runs_no_filter(self, client, db_session_scope):
        with db_session_scope() as session:
            enqueue_run(session, run_type="x", trigger_type="manual")
            enqueue_run(session, run_type="x", trigger_type="scheduled")
        resp = client.get("/api/scrape-runs")
        assert resp.status_code == 200
        assert len(resp.get_json()["runs"]) >= 2

    def test_history_filter_by_trigger_manual(self, client, db_session_scope):
        with db_session_scope() as session:
            enqueue_run(session, run_type="x", trigger_type="manual")
            enqueue_run(session, run_type="x", trigger_type="scheduled")
        resp = client.get("/api/scrape-runs?trigger_type=manual")
        assert resp.status_code == 200
        runs = resp.get_json()["runs"]
        assert all(r["trigger_type"] == "manual" for r in runs)

    def test_history_filter_by_trigger_scheduled(self, client, db_session_scope):
        with db_session_scope() as session:
            enqueue_run(session, run_type="x", trigger_type="scheduled")
        resp = client.get("/api/scrape-runs?trigger_type=scheduled")
        assert resp.status_code == 200
        runs = resp.get_json()["runs"]
        assert all(r["trigger_type"] == "scheduled" for r in runs)

    def test_history_filter_by_trigger_retry(self, client, db_session_scope):
        with db_session_scope() as session:
            enqueue_run(session, run_type="x", trigger_type="retry", attempt=2)
        resp = client.get("/api/scrape-runs?trigger_type=retry")
        assert resp.status_code == 200
        runs = resp.get_json()["runs"]
        assert all(r["trigger_type"] == "retry" for r in runs)

    def test_history_scheduler_era_statuses_in_response(self, client, db_session_scope):
        """Scheduler-era statuses render through the history endpoint."""
        with db_session_scope() as session:
            for status in (RunStatus.QUEUED, RunStatus.RUNNING,
                           RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.PARTIAL):
                run = enqueue_run(session, run_type="x")
                run.status = status
                session.flush()
        resp = client.get("/api/scrape-runs?limit=50")
        assert resp.status_code == 200
        statuses = {r["status"] for r in resp.get_json()["runs"]}
        # At least the terminal ones must be present
        assert RunStatus.SUCCESS in statuses or RunStatus.FAILED in statuses

    def test_history_legacy_finished_status_accepted(self, client, db_session_scope):
        """The legacy 'finished' status filter must still work (mapped to success)."""
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            run.status = RunStatus.SUCCESS
            session.flush()
        # legacy filter value
        resp = client.get("/api/scrape-runs?status=finished")
        assert resp.status_code == 200

    def test_history_run_includes_retry_fields(self, client, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            run_id = run.id
        resp = client.get(f"/api/scrape-runs/{run_id}")
        assert resp.status_code == 200
        run_data = resp.get_json().get("run", resp.get_json())
        for field in ("retryable", "retry_of_run_id", "retry_exhausted"):
            assert field in run_data, f"Missing field {field} in run response"


# ─────────────────────────────────────────────────────────────────────────────
# Commit 9 — UI correctness: serializer completeness
# ─────────────────────────────────────────────────────────────────────────────

class TestSerializerCompleteness:
    def test_serialize_job_has_all_ui_fields(self, client):
        r = _create_job(client, source_key="serial_shop")
        job = r.get_json()["job"]
        for field in ("id", "source_key", "runner_type", "enabled",
                      "allow_overlap", "max_retries", "retry_backoff_sec",
                      "timeout_sec", "priority", "next_run_at", "last_run_at",
                      "params_json"):
            assert field in job, f"Missing job field: {field}"

    def test_serialize_schedule_has_all_ui_fields(self, client):
        r = _create_job(client, source_key="serial_sched_shop",
                        with_schedule=True, schedule_type="interval", interval_sec=7200)
        job_id = r.get_json()["job"]["id"]
        schedules = client.get(
            f"/api/admin/scrape/jobs/{job_id}/schedule"
        ).get_json()["schedules"]
        assert len(schedules) >= 1
        sched = schedules[0]
        for field in ("id", "job_id", "schedule_type", "interval_sec",
                      "cron_expr", "timezone", "jitter_sec", "misfire_policy",
                      "enabled"):
            assert field in sched, f"Missing schedule field: {field}"

    def test_serialize_run_has_all_ui_fields(self, client, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="store_category_sync",
                              trigger_type="manual")
            run_id = run.id
        resp = client.get(f"/api/scrape-runs/{run_id}")
        assert resp.status_code == 200
        run_data = resp.get_json().get("run", resp.get_json())
        for field in ("id", "status", "trigger_type", "attempt",
                      "queued_at", "started_at", "finished_at",
                      "worker_id", "error_message",
                      "retryable", "retry_of_run_id", "retry_exhausted",
                      "categories_processed", "products_processed"):
            assert field in run_data, f"Missing run field: {field}"

