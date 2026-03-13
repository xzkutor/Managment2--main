"""app.py — Web runtime entry-point.

Responsibilities
----------------
- Re-export :func:`create_app` for Gunicorn and test compatibility.
- Create the process-level ``app`` instance used by ``gunicorn app:app``
  and ``python app.py``.
- Call ``start_scheduler_if_enabled`` — embedded dev-only scheduler
  autostart.  This call is intentionally NOT inside the factory so that
  dedicated runtime processes (scheduler, worker) can import the factory
  without triggering any embedded-scheduler side effect.

Gunicorn target::

    gunicorn app:app

Dev server::

    python app.py           # SCHEDULER_ENABLED / APP_ENV control autostart

Dedicated runtime processes MUST import ``create_app`` from
``pricewatch.app_factory``, NOT from this module, to avoid triggering
the global ``app = create_app()`` side effect.
"""
import logging

from pricewatch.app_factory import create_app  # noqa: F401 — re-exported for tests
from pricewatch.scrape.bootstrap import start_scheduler_if_enabled

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Web-runtime application instance
# ---------------------------------------------------------------------------
# This global is intentionally placed at module level so that:
#   - ``gunicorn app:app`` can locate it;
#   - ``flask run`` can locate it;
#   - ``from app import app`` in tests works without extra setup.
#
# Dedicated runtime modules (run_scheduler, run_worker) MUST NOT import
# from this module — import from ``pricewatch.app_factory`` instead.
# ---------------------------------------------------------------------------
app = create_app()

# Embedded scheduler autostart — dev-only convenience.
# Suppressed automatically when TESTING=True, APP_ENV=production, or
# SCHEDULER_ENABLED=False.  See pricewatch.scrape.bootstrap for full logic.
start_scheduler_if_enabled(app)


if __name__ == "__main__":
    app.run(debug=True, port=5000)

