"""pricewatch.scrape.run_scheduler -- Canonical scheduler process entrypoint.
Launch as::
    python -m pricewatch.scrape.run_scheduler
Dedicated production scheduler runtime. Must NOT be confused with the
embedded scheduler autostart in app.py, which is a development convenience
only (suppressed when APP_ENV=production).
Import path: imports create_app from pricewatch.app_factory (side-effect-free
factory), NOT from app.py. This prevents the module-level app = create_app()
side effect in app.py from running when dedicated entrypoints are used.
The scheduler detects due jobs, enqueues ScrapeRun records, and handles
retry orchestration. Does NOT serve HTTP or execute runner scraping logic.
Shutdown: Send SIGINT / KeyboardInterrupt for a clean exit.
"""
from __future__ import annotations
import logging
import sys
logger = logging.getLogger(__name__)
def main() -> None:
    """Initialize runtime context and enter the scheduler loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("run_scheduler: initializing application context")
    # Import from the isolated factory -- NOT from app.py
    from pricewatch.app_factory import create_app  # noqa: PLC0415
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
