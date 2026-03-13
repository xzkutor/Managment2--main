"""pricewatch.web.admin_scheduler_schedule_routes -- Scheduler schedule routes.

Routes
------
GET /api/admin/scrape/jobs/<job_id>/schedule
PUT /api/admin/scrape/jobs/<job_id>/schedule
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from pricewatch.db.repositories import (
    get_schedule_for_job,
    list_schedules_for_job,
    create_scrape_schedule,
    update_scrape_schedule,
)
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import serialize_scrape_schedule

logger = logging.getLogger(__name__)


def register_admin_scheduler_schedule_routes(bp: Blueprint) -> None:
    """Register scheduler schedule routes on the shared blueprint."""

    @bp.route("/api/admin/scrape/jobs/<int:job_id>/schedule", methods=["GET"])
    def api_get_job_schedule(job_id: int):
        session = get_db_session()()
        schedules = list_schedules_for_job(session, job_id)
        return jsonify({"schedules": [serialize_scrape_schedule(s) for s in schedules]})

    @bp.route("/api/admin/scrape/jobs/<int:job_id>/schedule", methods=["PUT"])
    def api_upsert_job_schedule(job_id: int):
        """Create or update the primary schedule for a job."""
        body = request.get_json(force=True, silent=True) or {}
        session = get_db_session()()
        try:
            existing = get_schedule_for_job(session, job_id)
            if existing:
                schedule = update_scrape_schedule(
                    session,
                    existing.id,
                    cron_expr=body.get("cron_expr"),
                    interval_sec=body.get("interval_sec"),
                    timezone=body.get("timezone"),
                    jitter_sec=body.get("jitter_sec"),
                    misfire_policy=body.get("misfire_policy"),
                    enabled=body.get("enabled"),
                )
            else:
                schedule = create_scrape_schedule(
                    session,
                    job_id=job_id,
                    schedule_type=body.get("schedule_type", "interval"),
                    cron_expr=body.get("cron_expr"),
                    interval_sec=body.get("interval_sec"),
                    timezone=body.get("timezone", "UTC"),
                    jitter_sec=body.get("jitter_sec", 0),
                    misfire_policy=body.get("misfire_policy", "skip"),
                    enabled=body.get("enabled", True),
                )
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("api_upsert_job_schedule failed: %s", exc)
            return jsonify({"error": str(exc)}), 400
        return jsonify({"schedule": serialize_scrape_schedule(schedule)})

