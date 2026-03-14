"""RFC-012 — ScrapeRun Semantics: tests that lock down clarified semantics.

Covers:
  Commit 1 — run-kind helpers (is_scheduler_owned / is_legacy_run)
  Commit 2 — retry_processed field existence and defaults
  Commit 3 — scheduler sets retry_processed not retry_exhausted on normal retry creation
  Commit 4 — attempt arithmetic and max_retries policy
  Commit 5 — canonical success status; finished compatibility
  Commit 6 — retry_of_run_id is the canonical retry lineage (not metadata_json)
  Commit 7 — trigger_type vs run_type semantics
  Commit 8 — serializer includes retry_processed
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from pricewatch.db.models import RunStatus, ScrapeRun
from pricewatch.db.repositories import (
    claim_next_queued_run,
    complete_run,
    create_scrape_job,
    enqueue_run,
    list_retry_candidates,
    get_run,
)
from pricewatch.services.scrape_history_service import ScrapeHistoryService, _normalize_status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _past(sec: int = 120) -> datetime:
    return _now() - timedelta(seconds=sec)


def _make_job(session, *, max_retries=1, retry_backoff_sec=60, allow_overlap=False):
    return create_scrape_job(
        session,
        source_key="semantics_test",
        runner_type="_test_semantics_runner",
        params_json={},
        enabled=True,
        allow_overlap=allow_overlap,
        max_retries=max_retries,
        retry_backoff_sec=retry_backoff_sec,
        next_run_at=_past(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Commit 1 — Run-kind helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestRunKindHelpers:
    """is_scheduler_owned and is_legacy_run are explicit and complementary."""

    def test_scheduler_owned_when_job_id_set(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            run = enqueue_run(session, job_id=job.id, run_type="x")
            assert run.is_scheduler_owned is True
            assert run.is_legacy_run is False

    def test_legacy_run_when_no_job_id(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            assert run.is_scheduler_owned is False
            assert run.is_legacy_run is True

    def test_helpers_are_mutually_exclusive(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            scheduler_run = enqueue_run(session, job_id=job.id, run_type="x")
            legacy_run = enqueue_run(session, run_type="x")
            assert scheduler_run.is_scheduler_owned != scheduler_run.is_legacy_run
            assert legacy_run.is_scheduler_owned != legacy_run.is_legacy_run


# ─────────────────────────────────────────────────────────────────────────────
# Commit 2 — retry_processed field existence and defaults
# ─────────────────────────────────────────────────────────────────────────────

class TestRetryProcessedField:
    def test_default_is_false_on_enqueue(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            assert run.retry_processed is False

    def test_default_is_false_after_complete_success(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.SUCCESS)
            r = get_run(session, run.id)
            assert r.retry_processed is False

    def test_default_is_false_after_complete_failed(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            r = get_run(session, run.id)
            # Worker does NOT set retry_processed — only the scheduler does
            assert r.retry_processed is False

    def test_serialize_run_includes_retry_processed(self, db_session_scope):
        from pricewatch.web.serializers import serialize_run
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            d = serialize_run(run)
        assert "retry_processed" in d
        assert d["retry_processed"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Commit 3 — Scheduler sets retry_processed (not retry_exhausted) on retry creation
# ─────────────────────────────────────────────────────────────────────────────

class TestSchedulerRetryProcessedSemantics:
    def test_retry_processed_true_retry_exhausted_false_after_retry_created(
        self, db_session_scope
    ):
        """When scheduler creates a retry child (budget NOT exhausted):
        - source.retry_processed must be True
        - source.retry_exhausted must remain False
        """
        from pricewatch.scrape.scheduler import run_tick

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

        assert r2.retry_processed is True, "scheduler must mark source as processed"
        assert r2.retry_exhausted is False, "budget NOT exhausted — retry was created"

    def test_both_flags_true_when_budget_exhausted(self, db_session_scope):
        """When scheduler cannot create a retry (budget exhausted):
        - source.retry_processed must be True
        - source.retry_exhausted must be True
        """
        from pricewatch.scrape.scheduler import run_tick

        backoff = 1
        with db_session_scope() as session:
            job = _make_job(session, max_retries=1, retry_backoff_sec=backoff)
            # attempt=2 exceeds max_retries=1 → budget exhausted
            run = enqueue_run(
                session, job_id=job.id, run_type=job.runner_type, attempt=2
            )
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            run_tick(session, now=_now())
            r2 = get_run(session, run.id)

        assert r2.retry_processed is True
        assert r2.retry_exhausted is True

    def test_retry_candidate_filter_uses_retry_processed(self, db_session_scope):
        """Once retry_processed=True, the run is no longer a candidate."""
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            # Simulate scheduler marking the run as processed
            r = get_run(session, run.id)
            r.retry_processed = True
            session.flush()
            candidates = list_retry_candidates(session)
        assert not any(c.id == run.id for c in candidates)

    def test_retry_candidate_not_excluded_while_retry_processed_false(
        self, db_session_scope
    ):
        """Before scheduler processes it, a retryable failed run IS a candidate."""
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            candidates = list_retry_candidates(session)
        assert any(c.id == run.id for c in candidates)


# ─────────────────────────────────────────────────────────────────────────────
# Commit 4 — Attempt arithmetic and max_retries policy
# ─────────────────────────────────────────────────────────────────────────────

class TestAttemptArithmetic:
    """max_retries = additional retries beyond the initial attempt (attempt=1)."""

    def test_max_retries_0_means_no_retry(self, db_session_scope):
        """max_retries=0 → attempt=1 exhausts budget immediately, no retry."""
        from pricewatch.scrape.scheduler import run_tick

        backoff = 1
        with db_session_scope() as session:
            job = _make_job(session, max_retries=0, retry_backoff_sec=backoff)
            run = enqueue_run(session, job_id=job.id, run_type=job.runner_type, attempt=1)
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            tick = run_tick(session, now=_now())
            r2 = get_run(session, run.id)

        assert len(tick.retries_enqueued) == 0, "no retry when max_retries=0"
        assert r2.retry_exhausted is True
        assert r2.retry_processed is True

    def test_max_retries_1_allows_exactly_one_retry(self, db_session_scope):
        """max_retries=1 → attempt=1 creates retry at attempt=2; attempt=2 exhausts."""
        from pricewatch.scrape.scheduler import run_tick

        backoff = 1
        with db_session_scope() as session:
            job = _make_job(session, max_retries=1, retry_backoff_sec=backoff)

            # Initial run (attempt=1) — should get a retry
            run1 = enqueue_run(
                session, job_id=job.id, run_type=job.runner_type, attempt=1
            )
            claim_next_queued_run(session, "w")
            complete_run(session, run1.id, status=RunStatus.FAILED, retryable=True)
            r1 = get_run(session, run1.id)
            r1.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            tick1 = run_tick(session, now=_now())

        assert len(tick1.retries_enqueued) == 1, "one retry should be created"

        with db_session_scope() as session:
            # Now simulate the retry run (attempt=2) failing
            retry_run = (
                session.query(ScrapeRun)
                .filter(ScrapeRun.retry_of_run_id == run1.id)
                .first()
            )
            assert retry_run is not None
            assert retry_run.attempt == 2

            claim_next_queued_run(session, "w")
            complete_run(session, retry_run.id, status=RunStatus.FAILED, retryable=True)
            rr = get_run(session, retry_run.id)
            rr.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            tick2 = run_tick(session, now=_now())
            rr2 = get_run(session, retry_run.id)

        assert len(tick2.retries_enqueued) == 0, "budget exhausted after 1 retry"
        assert rr2.retry_exhausted is True

    def test_retry_attempt_increments_correctly(self, db_session_scope):
        """Retry child has attempt = source.attempt + 1."""
        from pricewatch.scrape.scheduler import run_tick

        backoff = 1
        with db_session_scope() as session:
            job = _make_job(session, max_retries=3, retry_backoff_sec=backoff)
            run = enqueue_run(
                session, job_id=job.id, run_type=job.runner_type, attempt=1
            )
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            run_tick(session, now=_now())
            retry = (
                session.query(ScrapeRun)
                .filter(ScrapeRun.retry_of_run_id == run.id)
                .first()
            )

        assert retry is not None
        assert retry.attempt == 2


# ─────────────────────────────────────────────────────────────────────────────
# Commit 5 — Canonical success status
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalSuccessStatus:
    def test_complete_run_defaults_to_success(self, db_session_scope):
        """complete_run without explicit status must produce RunStatus.SUCCESS."""
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id)
            r = get_run(session, run.id)
        assert r.status == RunStatus.SUCCESS

    def test_finish_run_defaults_to_success(self, db_session_scope):
        """finish_run without explicit status must produce 'success' (RFC-012 §5.1)."""
        from pricewatch.db.repositories import finish_run
        with db_session_scope() as session:
            from pricewatch.db.repositories import start_run
            run = start_run(session, store_id=None, run_type="x")
            finish_run(session, run.id)
            r = get_run(session, run.id)
        assert r.status == RunStatus.SUCCESS

    def test_normalize_status_finished_maps_to_success(self):
        """Legacy 'finished' must normalize to 'success' in history service."""
        assert _normalize_status("finished") == RunStatus.SUCCESS

    def test_normalize_status_success_unchanged(self):
        assert _normalize_status("success") == RunStatus.SUCCESS

    def test_normalize_status_queued_unchanged(self):
        assert _normalize_status("queued") == "queued"

    def test_normalize_status_failed_unchanged(self):
        assert _normalize_status("failed") == "failed"

    def test_normalize_status_retry_not_remapped(self):
        """'retry' is a trigger_type value, not a run status — must not be remapped."""
        assert _normalize_status("retry") == "retry"

    def test_serialize_run_status_is_stored_value(self, db_session_scope):
        """serialize_run returns the stored status as-is (no remapping in serializer)."""
        from pricewatch.web.serializers import serialize_run
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED)
            r = get_run(session, run.id)
            d = serialize_run(r)
        assert d["status"] == RunStatus.FAILED


# ─────────────────────────────────────────────────────────────────────────────
# Commit 6 — retry_of_run_id is the canonical retry lineage
# ─────────────────────────────────────────────────────────────────────────────

class TestRetryLineage:
    def test_retry_child_has_retry_of_run_id(self, db_session_scope):
        """Retry child must have retry_of_run_id pointing to source — not only metadata."""
        from pricewatch.scrape.scheduler import run_tick

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
            retry = (
                session.query(ScrapeRun)
                .filter(ScrapeRun.retry_of_run_id == run.id)
                .first()
            )

        assert retry is not None
        assert retry.retry_of_run_id == run.id

    def test_retry_metadata_does_not_duplicate_retry_of_run_id(self, db_session_scope):
        """RFC-012 §5.3: metadata_json must not carry retry_of_run_id as canonical info.
        It may contain auxiliary data (source_key) but retry lineage lives in the column.
        """
        from pricewatch.scrape.scheduler import run_tick

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
            retry = (
                session.query(ScrapeRun)
                .filter(ScrapeRun.retry_of_run_id == run.id)
                .first()
            )

        assert retry is not None
        # The column IS the canonical lineage
        assert retry.retry_of_run_id == run.id
        # metadata_json must not duplicate retry lineage
        meta = retry.metadata_json or {}
        assert "retry_of_run_id" not in meta, (
            "metadata_json must not carry retry_of_run_id (RFC-012 §5.3)"
        )

    def test_serializer_exposes_retry_of_run_id(self, db_session_scope):
        from pricewatch.web.serializers import serialize_run
        with db_session_scope() as session:
            source = enqueue_run(session, run_type="x")
            child = enqueue_run(session, run_type="x", trigger_type="retry", attempt=2)
            child.retry_of_run_id = source.id
            session.flush()
            d = serialize_run(child)
        assert d["retry_of_run_id"] == source.id


# ─────────────────────────────────────────────────────────────────────────────
# Commit 7 — trigger_type vs run_type semantics
# ─────────────────────────────────────────────────────────────────────────────

class TestTriggerTypeVsRunType:
    """trigger_type = initiation cause; run_type = runner identity."""

    def test_scheduled_run_has_trigger_type_scheduled(self, db_session_scope):
        with db_session_scope() as session:
            job = _make_job(session)
            run = enqueue_run(
                session, job_id=job.id, run_type="store_category_sync",
                trigger_type="scheduled",
            )
            assert run.trigger_type == "scheduled"
            assert run.run_type == "store_category_sync"

    def test_manual_run_has_trigger_type_manual(self, db_session_scope):
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="full_scrape", trigger_type="manual")
            assert run.trigger_type == "manual"
            assert run.run_type == "full_scrape"

    def test_retry_run_has_trigger_type_retry(self, db_session_scope):
        from pricewatch.scrape.scheduler import run_tick

        backoff = 1
        with db_session_scope() as session:
            job = _make_job(session, max_retries=2, retry_backoff_sec=backoff)
            run = enqueue_run(
                session, job_id=job.id, run_type=job.runner_type, trigger_type="scheduled"
            )
            claim_next_queued_run(session, "w")
            complete_run(session, run.id, status=RunStatus.FAILED, retryable=True)
            r = get_run(session, run.id)
            r.finished_at = _now() - timedelta(seconds=backoff + 5)
            session.flush()
            run_tick(session, now=_now())
            retry = (
                session.query(ScrapeRun)
                .filter(ScrapeRun.retry_of_run_id == run.id)
                .first()
            )

        assert retry is not None
        assert retry.trigger_type == "retry"
        assert retry.run_type == job.runner_type  # run_type is inherited from job


# ─────────────────────────────────────────────────────────────────────────────
# Commit 8 — Serializer includes all RFC-012 fields
# ─────────────────────────────────────────────────────────────────────────────

class TestSerializerRFC012Fields:
    def test_all_retry_state_fields_present(self, db_session_scope):
        from pricewatch.web.serializers import serialize_run
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            d = serialize_run(run)
        for field in ("retryable", "retry_processed", "retry_exhausted", "retry_of_run_id"):
            assert field in d, f"serialize_run must include {field!r}"

    def test_retry_state_defaults_for_fresh_run(self, db_session_scope):
        from pricewatch.web.serializers import serialize_run
        with db_session_scope() as session:
            run = enqueue_run(session, run_type="x")
            d = serialize_run(run)
        assert d["retryable"] is False
        assert d["retry_processed"] is False
        assert d["retry_exhausted"] is False
        assert d["retry_of_run_id"] is None

    def test_trigger_type_and_run_type_in_serializer(self, db_session_scope):
        from pricewatch.web.serializers import serialize_run
        with db_session_scope() as session:
            run = enqueue_run(
                session, run_type="categories", trigger_type="scheduled"
            )
            d = serialize_run(run)
        assert d["trigger_type"] == "scheduled"
        assert d["run_type"] == "categories"

    def test_api_list_runs_includes_retry_processed(self, client, db_session_scope):
        with db_session_scope() as session:
            enqueue_run(session, run_type="x")

        resp = client.get("/api/scrape-runs")
        assert resp.status_code == 200
        runs = resp.get_json()["runs"]
        if runs:
            assert "retry_processed" in runs[0]

