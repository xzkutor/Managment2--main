"""tests/test_runtime_topology.py — Tests for production runtime topology.

Covers:
  Commit 1 — runtime_config module: APP_ENV parsing, is_production/is_development
  Commit 2 — production mode forbids embedded scheduler autostart
  Commit 3 — scheduler module entrypoint exists with canonical path
  Commit 4 — worker module entrypoint exists with canonical path
  Commit 5 — worker runtime status helper exists and has expected keys
  Commit 6 — /api/scrape-status includes nested scheduler, worker, queue sections
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _reset_bootstrap() -> None:
    """Reset process-local bootstrap state so tests are isolated."""
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


def _make_app(
    *,
    testing: bool = False,
    enabled: bool = True,
    autostart: bool = True,
    tick: int = 1,
    app_env: str | None = None,
) -> MagicMock:
    """Build a minimal mock Flask-like app object."""
    app = MagicMock()
    cfg: dict = {
        "TESTING":             testing,
        "SCHEDULER_ENABLED":   enabled,
        "SCHEDULER_AUTOSTART": autostart,
        "SCHEDULER_TICK_SECONDS": tick,
    }
    if app_env is not None:
        cfg["APP_ENV"] = app_env
    app.config = cfg
    fake_session = MagicMock()
    fake_session.return_value = MagicMock()
    app.extensions = {"db_scoped_session": fake_session}
    return app


# ---------------------------------------------------------------------------
# Commit 1 — runtime_config
# ---------------------------------------------------------------------------

class TestRuntimeConfig:

    def test_default_env_is_development(self):
        from pricewatch.scrape.runtime_config import get_app_env
        app = _make_app()               # no APP_ENV in config
        env_backup = os.environ.pop("APP_ENV", None)
        try:
            result = get_app_env(app)
        finally:
            if env_backup is not None:
                os.environ["APP_ENV"] = env_backup
        assert result == "development"

    def test_production_env_recognized(self):
        from pricewatch.scrape.runtime_config import is_production
        assert is_production(_make_app(app_env="production")) is True

    def test_prod_shorthand_recognized(self):
        from pricewatch.scrape.runtime_config import is_production
        assert is_production(_make_app(app_env="prod")) is True

    def test_development_env_recognized(self):
        from pricewatch.scrape.runtime_config import is_development
        assert is_development(_make_app(app_env="development")) is True

    def test_unknown_env_is_not_production(self):
        from pricewatch.scrape.runtime_config import is_production
        # "staging" is not in _PROD_VALUES — treated as non-production
        assert is_production(_make_app(app_env="staging")) is False

    def test_is_production_false_for_development(self):
        from pricewatch.scrape.runtime_config import is_production
        assert is_production(_make_app(app_env="development")) is False

    def test_scheduler_enabled_reads_config(self):
        from pricewatch.scrape.runtime_config import scheduler_enabled
        assert scheduler_enabled(_make_app(enabled=False)) is False
        assert scheduler_enabled(_make_app(enabled=True)) is True

    def test_scheduler_tick_seconds_reads_config(self):
        from pricewatch.scrape.runtime_config import scheduler_tick_seconds
        assert scheduler_tick_seconds(_make_app(tick=60)) == 60

    def test_worker_enabled_reads_config(self):
        from pricewatch.scrape.runtime_config import worker_enabled
        app = _make_app()
        app.config["WORKER_ENABLED"] = False
        assert worker_enabled(app) is False

    def test_worker_poll_interval_reads_config(self):
        from pricewatch.scrape.runtime_config import worker_poll_interval
        app = _make_app()
        app.config["WORKER_POLL_INTERVAL_SEC"] = 10
        assert worker_poll_interval(app) == 10.0

    def test_scheduler_autostart_reads_config(self):
        from pricewatch.scrape.runtime_config import scheduler_autostart
        assert scheduler_autostart(_make_app(autostart=False)) is False

    def test_env_var_fallback_when_no_app(self):
        """When no app is supplied, reads from os.environ."""
        from pricewatch.scrape.runtime_config import is_production
        old = os.environ.get("APP_ENV")
        try:
            os.environ["APP_ENV"] = "production"
            assert is_production(None) is True
        finally:
            if old is None:
                os.environ.pop("APP_ENV", None)
            else:
                os.environ["APP_ENV"] = old


# ---------------------------------------------------------------------------
# Commit 2 — production mode guard in bootstrap
# ---------------------------------------------------------------------------

class TestProductionSchedulerGuard:

    def setup_method(self):
        _reset_bootstrap()

    def test_production_mode_forbids_embedded_autostart(self):
        """APP_ENV=production must block embedded scheduler even with all flags True."""
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=False, enabled=True, autostart=True, app_env="production")
        assert should_start_scheduler(app) is False

    def test_prod_shorthand_forbids_embedded_autostart(self):
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=False, enabled=True, autostart=True, app_env="prod")
        assert should_start_scheduler(app) is False

    def test_production_mode_skip_reason_recorded(self):
        """skip_reason must mention 'production' when APP_ENV=production."""
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled, get_scheduler_runtime_status
        app = _make_app(testing=False, enabled=True, autostart=True, app_env="production")
        start_scheduler_if_enabled(app)
        status = get_scheduler_runtime_status()
        assert status["scheduler_skip_reason"] is not None
        assert "production" in status["scheduler_skip_reason"].lower()

    def test_production_mode_start_returns_false(self):
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled
        app = _make_app(testing=False, enabled=True, autostart=True, app_env="production")
        assert start_scheduler_if_enabled(app) is False

    def test_development_mode_allows_embedded_autostart(self):
        """APP_ENV=development must allow embedded scheduler when other flags permit."""
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=False, enabled=True, autostart=True, app_env="development")
        assert should_start_scheduler(app) is True

    def test_no_app_env_defaults_to_development(self):
        """When APP_ENV is absent from config and env, behavior defaults to development."""
        from pricewatch.scrape.bootstrap import should_start_scheduler
        env_backup = os.environ.pop("APP_ENV", None)
        try:
            app = _make_app(testing=False, enabled=True, autostart=True)
            # APP_ENV not in config, not in env → defaults to "development"
            assert should_start_scheduler(app) is True
        finally:
            if env_backup is not None:
                os.environ["APP_ENV"] = env_backup

    def test_testing_still_suppresses_even_in_dev(self):
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=True, enabled=True, autostart=True, app_env="development")
        assert should_start_scheduler(app) is False

    def test_scheduler_disabled_still_suppresses_in_dev(self):
        from pricewatch.scrape.bootstrap import should_start_scheduler
        app = _make_app(testing=False, enabled=False, autostart=True, app_env="development")
        assert should_start_scheduler(app) is False


# ---------------------------------------------------------------------------
# Commit 3 & 4 — canonical entrypoint modules
# ---------------------------------------------------------------------------

class TestEntrypointModulesExist:

    def test_run_scheduler_module_importable(self):
        import importlib
        module = importlib.import_module("pricewatch.scrape.run_scheduler")
        assert hasattr(module, "main"), "run_scheduler must expose a main() function"

    def test_run_worker_module_importable(self):
        import importlib
        module = importlib.import_module("pricewatch.scrape.run_worker")
        assert hasattr(module, "main"), "run_worker must expose a main() function"

    def test_run_scheduler_main_callable(self):
        from pricewatch.scrape.run_scheduler import main
        assert callable(main)

    def test_run_worker_main_callable(self):
        from pricewatch.scrape.run_worker import main
        assert callable(main)

    def test_run_scheduler_has_dunder_main_guard(self):
        """Module should support python -m pricewatch.scrape.run_scheduler."""
        import inspect
        import importlib
        source = inspect.getsource(importlib.import_module("pricewatch.scrape.run_scheduler"))
        assert '__name__' in source and 'main()' in source

    def test_run_worker_has_dunder_main_guard(self):
        """Module should support python -m pricewatch.scrape.run_worker."""
        import inspect
        import importlib
        source = inspect.getsource(importlib.import_module("pricewatch.scrape.run_worker"))
        assert '__name__' in source and 'main()' in source


# ---------------------------------------------------------------------------
# Commit 5 — worker runtime visibility
# ---------------------------------------------------------------------------

class TestWorkerRuntimeStatus:

    def test_get_worker_runtime_status_importable(self):
        from pricewatch.scrape.worker import get_worker_runtime_status
        assert callable(get_worker_runtime_status)

    def test_worker_status_has_expected_keys(self):
        from pricewatch.scrape.worker import get_worker_runtime_status
        status = get_worker_runtime_status()
        for key in (
            "worker_last_poll_at",
            "worker_last_claimed_run_id",
            "worker_last_completed_run_id",
            "worker_last_error",
            "worker_polls_total",
            "worker_runs_claimed_total",
        ):
            assert key in status, f"Missing key in worker status: {key}"

    def test_worker_status_numeric_counters_are_ints(self):
        from pricewatch.scrape.worker import get_worker_runtime_status
        status = get_worker_runtime_status()
        assert isinstance(status["worker_polls_total"], int)
        assert isinstance(status["worker_runs_claimed_total"], int)


# ---------------------------------------------------------------------------
# Commit 6 — /api/scrape-status nested sections
# ---------------------------------------------------------------------------

class TestScrapeStatusNestedSections:

    def test_has_scheduler_section(self, monkeypatch):
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "scheduler" in data, f"'scheduler' missing from: {list(data.keys())}"

    def test_has_worker_section(self, monkeypatch):
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "worker" in data, f"'worker' missing from: {list(data.keys())}"

    def test_has_queue_section(self, monkeypatch):
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "queue" in data, f"'queue' missing from: {list(data.keys())}"

    def test_queue_section_has_expected_keys(self, monkeypatch):
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        queue = resp.get_json()["queue"]
        assert "queued" in queue
        assert "running" in queue
        assert "failed_retryable" in queue

    def test_worker_section_has_expected_keys(self, monkeypatch):
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        worker = resp.get_json()["worker"]
        assert "worker_last_poll_at" in worker
        assert "worker_polls_total" in worker

    def test_scheduler_section_has_expected_keys(self, monkeypatch):
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        scheduler = resp.get_json()["scheduler"]
        assert "scheduler_running" in scheduler
        assert "scheduler_enabled" in scheduler

    def test_runs_key_preserved_for_backward_compat(self, monkeypatch):
        """Backward-compat: 'runs' key must remain in the response."""
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "runs" in data, "'runs' key must be preserved for backward compatibility"

    def test_defaults_to_running_status_filter(self, monkeypatch):
        """The status filter must default to 'running'."""
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        received: dict = {}

        def fake_list(self, *, store_id=None, run_type=None, status=None, limit=None, **kw):
            received["status"] = status
            return []

        monkeypatch.setattr(ScrapeHistoryService, "list_runs", fake_list)
        app.test_client().get("/api/scrape-status")
        assert received.get("status") == "running"

    def test_worker_section_has_running_and_started_at(self, monkeypatch):
        """Worker section must include 'running' and 'started_at' (Commit 4)."""
        from app import app
        from pricewatch.services.scrape_history_service import ScrapeHistoryService
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        worker = resp.get_json()["worker"]
        assert "running" in worker, f"'running' missing from worker section: {worker}"
        assert "started_at" in worker, f"'started_at' missing from worker section: {worker}"


# ---------------------------------------------------------------------------
# Commit 6 (follow-up) — Regression: side-effect-free factory and entrypoints
# ---------------------------------------------------------------------------

class TestSideEffectFreeFactory:

    def setup_method(self):
        _reset_bootstrap()

    def test_app_factory_module_importable_without_side_effects(self):
        """Importing pricewatch.app_factory must not create a global app or start scheduler."""
        import sys
        # Remove from cache to force fresh import (if already cached from earlier, fine)
        import importlib
        importlib.import_module("pricewatch.app_factory")
        # Scheduler must not have been started as a side effect of the import
        from pricewatch.scrape.bootstrap import get_scheduler_runtime_status
        status = get_scheduler_runtime_status()
        # importing the module alone must not start the scheduler
        assert status["scheduler_started"] is False

    def test_create_app_from_factory_does_not_start_scheduler(self):
        """create_app() from the isolated factory must NOT call start_scheduler_if_enabled."""
        from pricewatch.app_factory import create_app
        _reset_bootstrap()
        app = create_app({"TESTING": True})
        from pricewatch.scrape.bootstrap import get_scheduler_runtime_status
        status = get_scheduler_runtime_status()
        assert status["scheduler_started"] is False, (
            "create_app() from pricewatch.app_factory must not start the scheduler; "
            "only app.py (web entrypoint) should do that"
        )

    def test_run_scheduler_does_not_import_app_module(self):
        """run_scheduler source must reference pricewatch.app_factory, not app.py."""
        import inspect
        import importlib
        src = inspect.getsource(importlib.import_module("pricewatch.scrape.run_scheduler"))
        assert "pricewatch.app_factory" in src, \
            "run_scheduler must import from pricewatch.app_factory"
        # Must NOT do a bare 'from app import create_app'
        assert "from app import create_app" not in src, \
            "run_scheduler must not import create_app from app.py"

    def test_run_worker_does_not_import_app_module(self):
        """run_worker source must reference pricewatch.app_factory, not app.py."""
        import inspect
        import importlib
        src = inspect.getsource(importlib.import_module("pricewatch.scrape.run_worker"))
        assert "pricewatch.app_factory" in src, \
            "run_worker must import from pricewatch.app_factory"
        assert "from app import create_app" not in src, \
            "run_worker must not import create_app from app.py"

    def test_importing_run_scheduler_does_not_start_scheduler(self):
        """Importing run_scheduler (without calling main) must not start scheduler."""
        _reset_bootstrap()
        import importlib
        importlib.import_module("pricewatch.scrape.run_scheduler")
        from pricewatch.scrape.bootstrap import get_scheduler_runtime_status
        assert get_scheduler_runtime_status()["scheduler_started"] is False

    def test_importing_run_worker_does_not_start_scheduler(self):
        """Importing run_worker (without calling main) must not start scheduler."""
        _reset_bootstrap()
        import importlib
        importlib.import_module("pricewatch.scrape.run_worker")
        from pricewatch.scrape.bootstrap import get_scheduler_runtime_status
        assert get_scheduler_runtime_status()["scheduler_started"] is False

    def test_production_guard_blocks_web_embedded_scheduler(self):
        """Web bootstrap (start_scheduler_if_enabled) must be blocked in production."""
        from pricewatch.scrape.bootstrap import start_scheduler_if_enabled, get_scheduler_runtime_status
        app = _make_app(testing=False, enabled=True, autostart=True, app_env="production")
        _reset_bootstrap()
        result = start_scheduler_if_enabled(app)
        assert result is False
        assert "production" in (get_scheduler_runtime_status()["scheduler_skip_reason"] or "").lower()

    def test_app_factory_does_not_contain_global_app_creation(self):
        """pricewatch/app_factory.py must not have app = create_app() at module level."""
        import inspect
        import importlib
        src = inspect.getsource(importlib.import_module("pricewatch.app_factory"))
        # There should be no top-level assignment 'app = create_app()'
        lines = src.splitlines()
        for line in lines:
            stripped = line.strip()
            # Allow it inside function bodies only (indented)
            if stripped == "app = create_app()" and not line.startswith(" "):
                raise AssertionError(
                    "pricewatch/app_factory.py must not contain a top-level "
                    "'app = create_app()' side effect"
                )


# ---------------------------------------------------------------------------
# Commit 6 (follow-up) — Worker running/started_at state
# ---------------------------------------------------------------------------

class TestWorkerRunningState:

    def test_running_false_before_loop_starts(self):
        from pricewatch.scrape.worker import get_worker_runtime_status, _worker_lock, _worker_state
        with _worker_lock:
            _worker_state["running"]    = False
            _worker_state["started_at"] = None
        status = get_worker_runtime_status()
        assert status["running"] is False
        assert status["started_at"] is None

    def test_running_true_after_loop_starts(self):
        """After run_loop starts, running must be True and started_at set."""
        import threading
        from pricewatch.scrape.worker import run_loop, get_worker_runtime_status, _worker_lock, _worker_state
        # Reset state
        with _worker_lock:
            _worker_state["running"]    = False
            _worker_state["started_at"] = None
            _worker_state["polls_total"] = 0
        # Session factory that immediately returns nothing to claim
        calls = []
        class _FakeSession:
            def get_bind(self): return type("d", (), {"dialect": type("n", (), {"name": "sqlite"})()})()
            def query(self, *a, **kw):
                q = type("Q", (), {
                    "filter": lambda s, *a, **k: s,
                    "order_by": lambda s, *a, **k: s,
                    "first": lambda s: None,
                })()
                return q
            def rollback(self): pass
            def close(self): calls.append("close")
        def _factory():
            return _FakeSession()
        # Run one iteration then stop
        run_loop(_factory, idle_sleep_sec=0, max_iterations=1)
        status = get_worker_runtime_status()
        assert status["running"] is True
        assert status["started_at"] is not None
