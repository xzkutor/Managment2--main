"""pricewatch.scrape.bootstrap — Scheduler runtime autostart helper.

This module owns the decision of whether to start the scheduler background
thread and holds the process-local runtime state.

Public API
----------
- ``should_start_scheduler(app) -> bool``
- ``start_scheduler_if_enabled(app) -> bool``
- ``get_scheduler_runtime_status() -> dict``

Design rules (from plan)
------------------------
- No scheduler thread is ever started from import side effects.
- No worker startup code.
- No route imports.
- Process-local singleton guarded by a threading.Lock.
- State is held in the module-level ``_state`` dict — no external DB state.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Process-local runtime state
# ---------------------------------------------------------------------------
_lock  = threading.Lock()
_state: dict[str, Any] = {
    "started":      False,
    "thread":       None,        # threading.Thread | None
    "started_at":   None,        # datetime | None
    "last_tick_at": None,        # datetime | None
    "last_error":   None,        # str | None
    "skip_reason":  None,        # str | None  — why startup was skipped
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _cfg_bool(app: Any, key: str, default: bool = False) -> bool:
    """Read a boolean config value from Flask app.config or OS env."""
    import os  # noqa: PLC0415
    val = app.config.get(key)
    if val is None:
        # fall back to environment variable
        val = os.environ.get(key)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _cfg_int(app: Any, key: str, default: int) -> int:
    """Read an integer config value from Flask app.config or OS env."""
    import os  # noqa: PLC0415
    val = app.config.get(key)
    if val is None:
        val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def should_start_scheduler(app: Any) -> bool:
    """Return True when all conditions for scheduler autostart are met.

    Startup is denied when any of the following is true:
    - app is in testing context (``TESTING=True``);
    - ``SCHEDULER_ENABLED`` is falsy;
    - ``SCHEDULER_AUTOSTART`` is falsy.
    """
    if app.config.get("TESTING"):
        logger.debug("bootstrap: scheduler startup suppressed — TESTING=True")
        return False
    if not _cfg_bool(app, "SCHEDULER_ENABLED", default=True):
        logger.debug("bootstrap: scheduler startup suppressed — SCHEDULER_ENABLED=False")
        return False
    if not _cfg_bool(app, "SCHEDULER_AUTOSTART", default=True):
        logger.debug("bootstrap: scheduler startup suppressed — SCHEDULER_AUTOSTART=False")
        return False
    return True


def start_scheduler_if_enabled(app: Any) -> bool:
    """Start the scheduler background thread if config permits.

    Returns True if a thread was started in this call, False otherwise
    (already running, disabled, or test context).

    This function is idempotent — calling it multiple times in one process
    is safe; only the first call that passes the gate starts a thread.
    """
    with _lock:
        # --- Already running guard (Commit 5) ---
        thread: threading.Thread | None = _state["thread"]
        if thread is not None and thread.is_alive():
            reason = "scheduler thread already running"
            _state["skip_reason"] = reason
            logger.info("bootstrap: %s — skipping duplicate startup", reason)
            return False

        # --- Config gate (Commit 4) ---
        if not should_start_scheduler(app):
            # Record the most specific reason
            if app.config.get("TESTING"):
                _state["skip_reason"] = "TESTING context"
            elif not _cfg_bool(app, "SCHEDULER_ENABLED", default=True):
                _state["skip_reason"] = "SCHEDULER_ENABLED=False"
            else:
                _state["skip_reason"] = "SCHEDULER_AUTOSTART=False"
            return False

        tick_seconds = _cfg_int(app, "SCHEDULER_TICK_SECONDS", default=30)
        logger.info(
            "bootstrap: starting scheduler thread (tick_interval=%ds)", tick_seconds
        )

        # Capture app reference for use inside the thread
        _app = app

        def _loop() -> None:
            """Background scheduler loop — runs until process exit."""
            from pricewatch.scrape.scheduler import run_loop  # noqa: PLC0415
            logger.info("bootstrap: scheduler loop thread started")
            try:
                run_loop(
                    session_factory=lambda: _app.extensions["db_scoped_session"](),
                    tick_interval_sec=tick_seconds,
                    on_tick_start=_on_tick_start,
                    on_tick_done=_on_tick_done,
                    on_error=_on_loop_error,
                )
            except Exception as exc:  # pragma: no cover
                _on_loop_error(exc)
                logger.exception("bootstrap: scheduler loop exited with error: %s", exc)

        t = threading.Thread(target=_loop, name="pricewatch-scheduler", daemon=True)
        t.start()

        _state["started"]    = True
        _state["thread"]     = t
        _state["started_at"] = _utcnow()
        _state["skip_reason"] = None
        logger.info("bootstrap: scheduler thread started (daemon=True)")
        return True


def get_scheduler_runtime_status() -> dict[str, Any]:
    """Return a snapshot of the scheduler runtime state.

    Safe to call from any thread.  Suitable for inclusion in admin status
    endpoint responses.
    """
    with _lock:
        thread: threading.Thread | None = _state["thread"]
        running = thread is not None and thread.is_alive()
        return {
            "scheduler_running":    running,
            "scheduler_started":    _state["started"],
            "scheduler_started_at": (
                _state["started_at"].isoformat() if _state["started_at"] else None
            ),
            "scheduler_last_tick_at": (
                _state["last_tick_at"].isoformat() if _state["last_tick_at"] else None
            ),
            "scheduler_last_error": _state["last_error"],
            "scheduler_skip_reason": _state["skip_reason"],
        }


# ---------------------------------------------------------------------------
# Internal tick callbacks — called from inside the scheduler loop
# ---------------------------------------------------------------------------

def _on_tick_start() -> None:
    with _lock:
        _state["last_tick_at"] = _utcnow()


def _on_tick_done(tick: Any) -> None:  # tick: SchedulerTick
    with _lock:
        _state["last_tick_at"] = _utcnow()
        _state["last_error"]   = None


def _on_loop_error(exc: Exception) -> None:
    with _lock:
        _state["last_error"] = f"{type(exc).__name__}: {exc}"
    logger.error("bootstrap: scheduler loop error: %s", exc)

