"""pricewatch.scrape.run_worker -- Canonical worker process entrypoint.

Launch as::

    python -m pricewatch.scrape.run_worker

Dedicated production worker runtime. The worker must NOT be started
from the web runtime (app.py).

Import path: imports create_app from pricewatch.app_factory (side-effect-free
factory), NOT from app.py. This prevents the module-level app = create_app()
side effect in app.py from running when dedicated entrypoints are used.

The worker claims queued ScrapeRun records, resolves runner classes, and
executes them. It persists the retryable flag but must NOT enqueue
retry runs -- that is the scheduler responsibility (Decision 4).

Shutdown: Send SIGINT / KeyboardInterrupt for a clean exit.
"""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize runtime context and enter the worker polling loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    logger.info("run_worker: initializing application context")

    # Import from the isolated factory -- NOT from app.py -- to avoid the
    # global app = create_app() side effect that lives in app.py.
    from pricewatch.app_factory import create_app  # noqa: PLC0415
    from pricewatch.scrape.runtime_config import worker_poll_interval  # noqa: PLC0415
    from pricewatch.scrape.worker import run_loop  # noqa: PLC0415

    app = create_app()
    poll_sec = worker_poll_interval(app)

    logger.info("run_worker: starting worker loop (poll_interval=%.1fs)", poll_sec)

    with app.app_context():
        session_factory = lambda: app.extensions["db_scoped_session"]()  # noqa: E731

        try:
            run_loop(
                session_factory=session_factory,
                idle_sleep_sec=poll_sec,
            )
        except KeyboardInterrupt:
            logger.info("run_worker: shutdown requested via KeyboardInterrupt")
        except Exception as exc:
            logger.exception("run_worker: worker loop exited with error: %s", exc)
            sys.exit(1)


if __name__ == "__main__":
    main()
