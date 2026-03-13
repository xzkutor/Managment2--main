"""pricewatch.web.admin_scrape_history_routes -- Scrape history and status routes.

Routes
------
GET /api/scrape-runs
GET /api/scrape-runs/<run_id>
GET /api/scrape-status
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, current_app

from pricewatch.services.scrape_history_service import ScrapeHistoryService
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import serialize_run

logger = logging.getLogger(__name__)


def register_admin_scrape_history_routes(bp: Blueprint) -> None:
    """Register scrape history and status routes on the shared blueprint."""

    @bp.route("/api/scrape-runs", methods=["GET"])
    def api_list_runs():
        session = get_db_session()()
        store_id     = request.args.get("store_id", type=int)
        run_type     = request.args.get("run_type")
        status       = request.args.get("status")
        trigger_type = request.args.get("trigger_type")
        limit  = request.args.get("limit",  type=int)
        offset = request.args.get("offset", type=int)
        service = ScrapeHistoryService(session)
        runs = service.list_runs(
            store_id=store_id, run_type=run_type, status=status,
            trigger_type=trigger_type, limit=limit, offset=offset,
        )
        return jsonify({"runs": [serialize_run(r) for r in runs]})

    @bp.route("/api/scrape-runs/<int:run_id>", methods=["GET"])
    def api_get_run(run_id: int):
        session = get_db_session()()
        service = ScrapeHistoryService(session)
        try:
            run = service.get_run(run_id)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify({"run": serialize_run(run)})

    @bp.route("/api/scrape-status", methods=["GET"])
    def api_scrape_status():
        """Aggregated operator runtime status endpoint.

        Returns nested sections:
          - ``runs``      -- recent runs (backward-compat, status filter applied)
          - ``scheduler`` -- process-local scheduler runtime state + config flags
          - ``worker``    -- process-local worker runtime state
          - ``queue``     -- DB-derived queue stats
        """
        session = get_db_session()()
        store_id = request.args.get("store_id", type=int)
        run_type = request.args.get("run_type")
        status = request.args.get("status") or "running"
        limit = request.args.get("limit", type=int) or 5
        service = ScrapeHistoryService(session)
        runs = service.list_runs(
            store_id=store_id, run_type=run_type, status=status, limit=limit
        )

        # --- Scheduler section ---
        from pricewatch.scrape.bootstrap import get_scheduler_runtime_status  # noqa: PLC0415
        from pricewatch.scrape.runtime_config import scheduler_enabled, scheduler_autostart  # noqa: PLC0415

        scheduler_section = get_scheduler_runtime_status()
        scheduler_section["scheduler_enabled"]   = scheduler_enabled(current_app)
        scheduler_section["scheduler_autostart"] = scheduler_autostart(current_app)

        # --- Worker section ---
        from pricewatch.scrape.worker import get_worker_runtime_status  # noqa: PLC0415

        worker_section = get_worker_runtime_status()

        # --- Queue section ---
        from pricewatch.db.repositories import get_queue_stats  # noqa: PLC0415

        try:
            queue_section = get_queue_stats(session)
        except Exception as exc:
            logger.warning("api_scrape_status: could not fetch queue stats: %s", exc)
            queue_section = {"queued": None, "running": None, "failed_retryable": None}

        return jsonify({
            "runs":      [serialize_run(r) for r in runs],
            "scheduler": scheduler_section,
            "worker":    worker_section,
            "queue":     queue_section,
        })

