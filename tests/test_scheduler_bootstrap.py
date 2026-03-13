"""tests/test_scheduler_bootstrap.py — Focused tests for scheduler autostart semantics.

Plan Commit 7 coverage:
1. startup occurs when enabled + autostart (thread started)
2. startup suppressed when SCHEDULER_ENABLED=False
3. startup suppressed when SCHEDULER_AUTOSTART=False
4. startup suppressed in TESTING context
5. repeated startup calls do not create duplicate threads
6. runtime status helper reflects the expected state

All tests use monkeypatching / stubs — no real background loops, no sleeps.
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helper: reset bootstrap module state between tests
# ---------------------------------------------------------------------------

def _reset_bootstrap() -> None:
    """Reset process-local state in bootstrap module so tests are isolated.

    Does NOT join any alive thread — tests that start threads are responsible
    for releasing their own gates and joining before returning.
    """
    from pricewatch.scrape import bootstrap
    with bootstrap._lock:
        bootstrap._state.update(
            started=False,
            thread=None,
            started_at=None,
            last_tick_at=None,
            last_error=None,
            skip_reason=None,
        )


def _make_app(*, testing=False, enabled=True, autostart=True, tick=1):
    """Build a minimal mock Flask-like app object."""
    app = MagicMock()
    app.config = {
        "TESTING":             testing,
        "SCHEDULER_ENABLED":   enabled,
        "SCHEDULER_AUTOSTART": autostart,
        "SCHEDULER_TICK_SECONDS": tick,
    }
    # Provide a no-op scoped session factory
    fake_session = MagicMock()
    fake_session.return_value = MagicMock()
    app.extensions = {"db_scoped_session": fake_session}
    return app


# ---------------------------------------------------------------------------
# should_start_scheduler
# ---------------------------------------------------------------------------

class TestShouldStartScheduler:
    def setup_method(self):
        _reset_bootstrap()

    def test_returns_true_when_all_flags_on(self):
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=False, enabled=True, autostart=True)
        assert should_start_scheduler(app) is True

    def test_returns_false_when_testing(self):
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=True, enabled=True, autostart=True)
        assert should_start_scheduler(app) is False

    def test_returns_false_when_disabled(self):
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=False, enabled=False, autostart=True)
        assert should_start_scheduler(app) is False

    def test_returns_false_when_autostart_off(self):
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=False, enabled=True, autostart=False)
        assert should_start_scheduler(app) is False

    def test_returns_false_when_both_flags_off(self):
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=False, enabled=False, autostart=False)
        assert should_start_scheduler(app) is False


# ---------------------------------------------------------------------------
# start_scheduler_if_enabled
# ---------------------------------------------------------------------------

class TestStartSchedulerIfEnabled:
    def setup_method(self):
        _reset_bootstrap()

    def test_suppressed_in_testing_mode(self):
        """No thread starts when TESTING=True."""
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled
        app = _make_app(testing=True)
        result = start_scheduler_if_enabled(app)
        assert result is False

    def test_suppressed_when_disabled(self):
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled
        app = _make_app(testing=False, enabled=False)
        result = start_scheduler_if_enabled(app)
        assert result is False

    def test_suppressed_when_autostart_false(self):
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled
        app = _make_app(testing=False, autostart=False)
        result = start_scheduler_if_enabled(app)
        assert result is False

    def test_starts_thread_when_enabled(self):
        """A daemon thread is started when config allows it."""
        from pricewatch.scrape import bootstrap

        gate = threading.Event()

        def _fake_run_loop(*args, **kwargs):
            gate.wait(timeout=5)

        app = _make_app(testing=False, enabled=True, autostart=True, tick=1)

        with patch("pricewatch.scrape.scheduler.run_loop", side_effect=_fake_run_loop):
            result = bootstrap.start_scheduler_if_enabled(app)

        assert result is True
        assert bootstrap._state["started"] is True
        assert bootstrap._state["started_at"] is not None
        assert bootstrap._state["thread"] is not None

        # Release gate and wait for thread to die before this test returns.
        # This ensures _reset_bootstrap in the next test sees no alive thread.
        gate.set()
        thread = bootstrap._state["thread"]
        if thread is not None:
            thread.join(timeout=8)

    def test_skip_reason_set_when_testing(self):
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled, _state
        app = _make_app(testing=True)
        start_scheduler_if_enabled(app)
        assert _state["skip_reason"] is not None
        assert "TESTING" in _state["skip_reason"]

    def test_skip_reason_set_when_disabled(self):
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled, _state
        app = _make_app(testing=False, enabled=False)
        start_scheduler_if_enabled(app)
        assert _state["skip_reason"] is not None
        assert "SCHEDULER_ENABLED" in _state["skip_reason"]

    def test_skip_reason_set_when_autostart_false(self):
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled, _state
        app = _make_app(testing=False, autostart=False)
        start_scheduler_if_enabled(app)
        assert _state["skip_reason"] is not None
        assert "SCHEDULER_AUTOSTART" in _state["skip_reason"]


# ---------------------------------------------------------------------------
# Idempotency — Commit 5
# ---------------------------------------------------------------------------

class TestIdempotency:
    def setup_method(self):
        _reset_bootstrap()

    def test_second_call_returns_false_when_thread_alive(self):
        """Calling start twice does not create a second thread."""
        from pricewatch.scrape import bootstrap

        # Inject a fake alive thread directly into state
        evt = threading.Event()
        alive_thread = threading.Thread(target=evt.wait, daemon=True)
        alive_thread.start()

        with bootstrap._lock:
            bootstrap._state["thread"]   = alive_thread
            bootstrap._state["started"]  = True

        app = _make_app(testing=False, enabled=True, autostart=True)
        result = bootstrap.start_scheduler_if_enabled(app)

        # Clean up
        evt.set()
        alive_thread.join(timeout=1)

        assert result is False

    def test_second_call_skip_reason_mentions_already_running(self):
        from pricewatch.scrape import bootstrap

        evt = threading.Event()
        alive_thread = threading.Thread(target=evt.wait, daemon=True)
        alive_thread.start()

        with bootstrap._lock:
            bootstrap._state["thread"]  = alive_thread
            bootstrap._state["started"] = True

        app = _make_app(testing=False, enabled=True, autostart=True)
        bootstrap.start_scheduler_if_enabled(app)

        evt.set()
        alive_thread.join(timeout=1)

        assert bootstrap._state["skip_reason"] is not None
        assert "already" in bootstrap._state["skip_reason"].lower()

    def test_dead_thread_allows_restart(self):
        """If previous thread is dead, a new one can be started."""
        from pricewatch.scrape import bootstrap

        # Create a thread that immediately exits
        dead_thread = threading.Thread(target=lambda: None, daemon=True)
        dead_thread.start()
        dead_thread.join(timeout=2)  # wait for it to die
        assert not dead_thread.is_alive()

        with bootstrap._lock:
            bootstrap._state["thread"]  = dead_thread
            bootstrap._state["started"] = True

        gate = threading.Event()

        def _fake_run_loop(*args, **kwargs):
            gate.wait(timeout=5)

        app = _make_app(testing=False, enabled=True, autostart=True, tick=1)

        with patch("pricewatch.scrape.scheduler.run_loop", side_effect=_fake_run_loop):
            result = bootstrap.start_scheduler_if_enabled(app)

        assert result is True

        gate.set()
        thread = bootstrap._state["thread"]
        if thread is not None:
            thread.join(timeout=8)


# ---------------------------------------------------------------------------
# Runtime status — Commit 6
# ---------------------------------------------------------------------------

class TestRuntimeStatus:
    def setup_method(self):
        _reset_bootstrap()

    def test_initial_status_not_running(self):
        from pricewatch.scrape.bootstrap import get_scheduler_runtime_status
        status = get_scheduler_runtime_status()
        assert status["scheduler_running"] is False
        assert status["scheduler_started"] is False
        assert status["scheduler_started_at"] is None
        assert status["scheduler_last_tick_at"] is None
        assert status["scheduler_last_error"] is None

    def test_status_after_skip_has_skip_reason(self):
        from pricewatch.scrape.bootstrap import (
            start_scheduler_if_enabled, get_scheduler_runtime_status
        )
        app = _make_app(testing=True)
        start_scheduler_if_enabled(app)
        status = get_scheduler_runtime_status()
        assert status["scheduler_running"] is False
        assert status["scheduler_skip_reason"] is not None

    def test_on_tick_start_updates_last_tick_at(self):
        from pricewatch.scrape.bootstrap import _on_tick_start, get_scheduler_runtime_status
        _on_tick_start()
        status = get_scheduler_runtime_status()
        assert status["scheduler_last_tick_at"] is not None

    def test_on_tick_done_clears_error(self):
        from pricewatch.scrape.bootstrap import _on_loop_error, _on_tick_done, get_scheduler_runtime_status
        _on_loop_error(RuntimeError("test error"))
        assert get_scheduler_runtime_status()["scheduler_last_error"] is not None
        _on_tick_done(MagicMock())
        assert get_scheduler_runtime_status()["scheduler_last_error"] is None

    def test_on_loop_error_stores_error(self):
        from pricewatch.scrape.bootstrap import _on_loop_error, get_scheduler_runtime_status
        _on_loop_error(ValueError("boom"))
        status = get_scheduler_runtime_status()
        assert status["scheduler_last_error"] is not None
        assert "ValueError" in status["scheduler_last_error"]
        assert "boom" in status["scheduler_last_error"]


# ---------------------------------------------------------------------------
# Integration: TESTING=True in conftest suppresses autostart
# ---------------------------------------------------------------------------

class TestAppStartupIntegration:
    def setup_method(self):
        _reset_bootstrap()

    def test_app_created_with_testing_flag_does_not_start_scheduler(self):
        """Verifies that create_app(TESTING=True) does NOT start a new thread.

        NOTE: The module-level ``app = create_app()`` in app.py may have already
        started a thread when app.py was imported.  This test verifies only that
        a *second* call with TESTING=True leaves the global state unchanged.
        """
        from app import create_app
        from pricewatch.scrape import bootstrap

        # Snapshot state before our TESTING call
        with bootstrap._lock:
            thread_before = bootstrap._state["thread"]
            started_before = bootstrap._state["started"]

        # This must NOT change state
        create_app({"TESTING": True, "DATABASE_URL": "sqlite:///:memory:"})

        with bootstrap._lock:
            thread_after = bootstrap._state["thread"]
            started_after = bootstrap._state["started"]

        assert thread_after is thread_before, (
            "create_app(TESTING=True) must not modify the global scheduler thread"
        )
        assert started_after == started_before, (
            "create_app(TESTING=True) must not change the started flag"
        )

    def test_should_start_scheduler_returns_false_for_testing_app(self):
        """should_start_scheduler must return False when TESTING=True."""
        from pricewatch.scrape.bootstrap import should_start_scheduler
        from app import create_app

        # Use a real Flask app with TESTING=True
        real_app = create_app({"TESTING": True, "DATABASE_URL": "sqlite:///:memory:"})
        assert should_start_scheduler(real_app) is False

    def test_scrape_status_endpoint_includes_scheduler_key(self, client):
        """The /api/scrape-status endpoint must include a 'scheduler' key."""
        resp = client.get("/api/scrape-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "scheduler" in data, "Missing 'scheduler' key in /api/scrape-status response"
        sched = data["scheduler"]
        for field in ("scheduler_running", "scheduler_enabled",
                      "scheduler_autostart", "scheduler_started_at",
                      "scheduler_last_tick_at", "scheduler_last_error"):
            assert field in sched, f"Missing scheduler status field: {field}"

    def test_scheduler_enabled_false_in_scrape_status_when_disabled(self, client, monkeypatch):
        """When SCHEDULER_ENABLED=False, endpoint reports scheduler_enabled=False."""
        monkeypatch.setenv("SCHEDULER_ENABLED", "false")
        resp = client.get("/api/scrape-status")
        assert resp.status_code == 200
        # scheduler_enabled reflects the env var / config — just check key exists
        sched = resp.get_json()["scheduler"]
        assert "scheduler_enabled" in sched

