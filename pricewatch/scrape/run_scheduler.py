"""pricewatch.scrape.run_scheduler — Canonical scheduler process entrypoint.

Launch as::

    python -m pricewatch.scrape.run_scheduler

This is the **dedicated production scheduler runtime**.  It must NOT be
confused with the embedded scheduler autostart in ``app.py``, which is a
development convenience only (and is suppressed when ``APP_ENV=production``).

The scheduler detects due jobs, enqueues ScrapeRun records, and handles
retry orchestration.  It does NOT serve HTTP and does NOT execute runner
scraping logic — that is the worker's responsibility.

Shutdown:
    Send SIGINT / KeyboardInterrupt for a clean exit.
"""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize runtime context and enter the scheduler loop.

    Steps
    -----
    1. Configure root logging.
    2. Create Flask app (DB wiring, config).
    3. Read tick interval from runtime config.
    4. Enter ``scheduler.run_loop`` — blocks until interrupted or error.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    logger.info("run_scheduler: initializing application context")

    # Deferred imports so this module is safe to import in tests without
    # triggering heavy side effects.
    from app import create_app  # noqa: PLC0415
    from pricewatch.scrape.runtime_config import scheduler_tick_seconds  # noqa: PLC0415
    from pricewatch.scrape.scheduler import run_loop  # noqa: PLC0415

    app = create_app()
    tick = scheduler_tick_seconds(app)

    logger.info("run_scheduler: starting scheduler loop (tick_interval=%ds)", tick)

    with app.app_context():
        session_factory = lambda: app.extensions["db_scoped_session"]()  # noqa: E731

        try:
            run_loop(
                session_factory=session_factory,
                tick_interval_sec=tick,
            )
        except KeyboardInterrupt:
            logger.info("run_scheduler: shutdown requested via KeyboardInterrupt")
        except Exception as exc:
            logger.exception("run_scheduler: scheduler loop exited with error: %s", exc)
            sys.exit(1)


if __name__ == "__main__":
    main()

