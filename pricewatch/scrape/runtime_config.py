"""pricewatch.scrape.runtime_config — Centralized runtime configuration helper.

Responsibilities
----------------
- Parse and expose APP_ENV runtime marker (development / production).
- Provide is_development() and is_production() guards.
- Read and expose scheduler/worker runtime config flags.
- All reads consult Flask app.config first, then os.environ as fallback.

Design rules
------------
- No Flask import at module level (importable without Flask).
- No background thread usage.
- No DB session usage.
- This module is the single authoritative source for runtime-mode decisions.

APP_ENV values
--------------
- ``production`` / ``prod``  → production mode (strong guards apply).
- ``development`` / ``dev`` / ``local`` / anything else → development mode.
- Absent → defaults to ``development``.
"""
from __future__ import annotations

import os
from typing import Any

# ---------------------------------------------------------------------------
# APP_ENV canonicalization
# ---------------------------------------------------------------------------

_PROD_VALUES: frozenset[str] = frozenset({"production", "prod"})


def get_app_env(app: Any = None) -> str:
    """Return APP_ENV value (lowercased and stripped).

    Checks Flask ``app.config`` first, then ``os.environ``, then defaults to
    ``"development"``.
    """
    val = None
    if app is not None:
        val = app.config.get("APP_ENV")
    if val is None:
        val = os.environ.get("APP_ENV")
    if val is None:
        return "development"
    return str(val).strip().lower()


def is_production(app: Any = None) -> bool:
    """Return True when APP_ENV indicates a production environment."""
    return get_app_env(app) in _PROD_VALUES


def is_development(app: Any = None) -> bool:
    """Return True when APP_ENV indicates a non-production environment."""
    return not is_production(app)


# ---------------------------------------------------------------------------
# Low-level config readers
# ---------------------------------------------------------------------------

def _read_bool(app: Any, key: str, default: bool) -> bool:
    """Read a boolean config value from app.config then os.environ."""
    val = None
    if app is not None:
        val = app.config.get(key)
    if val is None:
        val = os.environ.get(key)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _read_int(app: Any, key: str, default: int) -> int:
    """Read an integer config value from app.config then os.environ."""
    val = None
    if app is not None:
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
# Scheduler helpers
# ---------------------------------------------------------------------------

def scheduler_enabled(app: Any = None) -> bool:
    """Return True when SCHEDULER_ENABLED is truthy (default: True)."""
    return _read_bool(app, "SCHEDULER_ENABLED", default=True)


def scheduler_autostart(app: Any = None) -> bool:
    """Return True when SCHEDULER_AUTOSTART is truthy (default: True)."""
    return _read_bool(app, "SCHEDULER_AUTOSTART", default=True)


def scheduler_tick_seconds(app: Any = None) -> int:
    """Return SCHEDULER_TICK_SECONDS as int (default: 30)."""
    return _read_int(app, "SCHEDULER_TICK_SECONDS", default=30)


# ---------------------------------------------------------------------------
# Worker helpers
# ---------------------------------------------------------------------------

def worker_enabled(app: Any = None) -> bool:
    """Return True when WORKER_ENABLED is truthy (default: True)."""
    return _read_bool(app, "WORKER_ENABLED", default=True)


def worker_poll_interval(app: Any = None) -> float:
    """Return WORKER_POLL_INTERVAL_SEC as float (default: 5.0)."""
    return float(_read_int(app, "WORKER_POLL_INTERVAL_SEC", default=5))

