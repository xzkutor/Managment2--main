"""pricewatch.web.admin_scheduler_job_routes -- Scheduler job control-plane routes.

Routes
------
GET    /api/admin/scrape/jobs
POST   /api/admin/scrape/jobs
GET    /api/admin/scrape/jobs/<job_id>
PATCH  /api/admin/scrape/jobs/<job_id>
POST   /api/admin/scrape/jobs/<job_id>/run
GET    /api/admin/scrape/jobs/<job_id>/runs
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from pricewatch.db.repositories import (
    create_scrape_job,
    get_scrape_job,
    list_scrape_jobs,
    update_scrape_job,
    enqueue_run,
    list_runs_for_job,
    create_scrape_schedule,
    get_schedule_for_job,
    list_schedules_for_job,
    has_active_run_for_job,
)
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import (
    serialize_scrape_job,
    serialize_scrape_schedule,
    serialize_run,
)

logger = logging.getLogger(__name__)


def register_admin_scheduler_job_routes(bp: Blueprint) -> None:
    """Register scheduler job control-plane routes on the shared blueprint."""

    @bp.route("/api/admin/scrape/jobs", methods=["GET"])
    def api_list_scrape_jobs():
        """List all registered scrape jobs."""
        session = get_db_session()()
        enabled = request.args.get("enabled", type=lambda v: v.lower() == "true")
        runner_type = request.args.get("runner_type")
        limit = request.args.get("limit", type=int)
        offset = request.args.get("offset", type=int)
        jobs = list_scrape_jobs(
            session, enabled=enabled, runner_type=runner_type, limit=limit, offset=offset
        )
        return jsonify({"jobs": [serialize_scrape_job(j) for j in jobs]})

    @bp.route("/api/admin/scrape/jobs", methods=["POST"])
    def api_create_scrape_job():
        """Create a new scrape job (optionally with an initial schedule)."""
        body = request.get_json(force=True, silent=True) or {}
        source_key = body.get("source_key")
        runner_type = body.get("runner_type")
        if not source_key or not runner_type:
            return jsonify({"error": "source_key and runner_type are required"}), 400
        session = get_db_session()()
        try:
            job = create_scrape_job(
                session,
                source_key=source_key,
                runner_type=runner_type,
                params_json=body.get("params_json"),
                enabled=body.get("enabled", True),
                priority=body.get("priority", 0),
                allow_overlap=body.get("allow_overlap", False),
                timeout_sec=body.get("timeout_sec"),
                max_retries=body.get("max_retries", 0),
                retry_backoff_sec=body.get("retry_backoff_sec", 60),
                concurrency_key=body.get("concurrency_key"),
                next_run_at=None,
            )
            # Optionally create initial schedule
            schedule_data = body.get("schedule")
            schedule = None
            if schedule_data:
                schedule = create_scrape_schedule(
                    session,
                    job_id=job.id,
                    schedule_type=schedule_data.get("schedule_type", "interval"),
                    cron_expr=schedule_data.get("cron_expr"),
                    interval_sec=schedule_data.get("interval_sec"),
                    timezone=schedule_data.get("timezone", "UTC"),
                    jitter_sec=schedule_data.get("jitter_sec", 0),
                    misfire_policy=schedule_data.get("misfire_policy", "skip"),
                    enabled=schedule_data.get("enabled", True),
                )
                # Compute initial next_run_at
                from pricewatch.scrape.schedule import compute_next_run  # noqa: PLC0415
                from datetime import datetime, timezone as _tz  # noqa: PLC0415
                now = datetime.now(_tz.utc)
                try:
                    next_run = compute_next_run(
                        schedule.schedule_type,  # type: ignore[arg-type]
                        from_dt=now,
                        cron_expr=schedule.cron_expr,
                        interval_sec=schedule.interval_sec,
                        tz_name=schedule.timezone or "UTC",
                        jitter_sec=schedule.jitter_sec or 0,
                    )
                    from pricewatch.db.repositories import set_job_next_run_at  # noqa: PLC0415
                    set_job_next_run_at(session, job.id, next_run)
                except Exception as exc:
                    logger.warning("api_create_scrape_job: could not compute next_run_at: %s", exc)

            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("api_create_scrape_job failed: %s", exc)
            return jsonify({"error": str(exc)}), 400

        result_payload: dict = {"job": serialize_scrape_job(job)}
        if schedule is not None:
            result_payload["schedule"] = serialize_scrape_schedule(schedule)
        return jsonify(result_payload), 201

    @bp.route("/api/admin/scrape/jobs/<int:job_id>", methods=["GET"])
    def api_get_scrape_job(job_id: int):
        session = get_db_session()()
        job = get_scrape_job(session, job_id)
        if not job:
            return jsonify({"error": f"ScrapeJob {job_id} not found"}), 404
        schedules = list_schedules_for_job(session, job_id)
        return jsonify({
            "job": serialize_scrape_job(job),
            "schedules": [serialize_scrape_schedule(s) for s in schedules],
        })

    @bp.route("/api/admin/scrape/jobs/<int:job_id>", methods=["PATCH"])
    def api_update_scrape_job(job_id: int):
        body = request.get_json(force=True, silent=True) or {}
        session = get_db_session()()
        try:
            job = update_scrape_job(
                session,
                job_id,
                enabled=body.get("enabled"),
                priority=body.get("priority"),
                allow_overlap=body.get("allow_overlap"),
                timeout_sec=body.get("timeout_sec"),
                max_retries=body.get("max_retries"),
                retry_backoff_sec=body.get("retry_backoff_sec"),
                concurrency_key=body.get("concurrency_key"),
                params_json=body.get("params_json"),
            )
            session.commit()
        except ValueError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            session.rollback()
            logger.exception("api_update_scrape_job failed: %s", exc)
            return jsonify({"error": str(exc)}), 400
        return jsonify({"job": serialize_scrape_job(job)})

    @bp.route("/api/admin/scrape/jobs/<int:job_id>/run", methods=["POST"])
    def api_manual_enqueue_job(job_id: int):
        """Manually enqueue a run for a job (uses same queued-run model as scheduler).

        Overlap policy (Decision 2 -- RFC-008 addendum):
          If job.allow_overlap is False and an active run already exists,
          returns 409 Conflict.
        """
        session = get_db_session()()
        job = get_scrape_job(session, job_id)
        if not job:
            return jsonify({"error": f"ScrapeJob {job_id} not found"}), 404

        # Overlap guard -- Decision 2
        if not job.allow_overlap and has_active_run_for_job(session, job_id):
            return jsonify({
                "error": "conflict",
                "message": (
                    f"Job {job_id} has an active run and allow_overlap is False. "
                    "Wait for the active run to finish or set allow_overlap=True."
                ),
            }), 409

        body = request.get_json(force=True, silent=True) or {}
        try:
            run = enqueue_run(
                session,
                job_id=job_id,
                run_type=job.runner_type,
                trigger_type="manual",
                metadata_json=body.get("metadata_json") or {"source_key": job.source_key},
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("api_manual_enqueue_job failed: %s", exc)
            return jsonify({"error": str(exc)}), 400
        return jsonify({"run": serialize_run(run)}), 202

    @bp.route("/api/admin/scrape/jobs/<int:job_id>/runs", methods=["GET"])
    def api_list_runs_for_job(job_id: int):
        session = get_db_session()()
        status = request.args.get("status")
        limit = request.args.get("limit", type=int)
        offset = request.args.get("offset", type=int)
        runs = list_runs_for_job(session, job_id, status=status, limit=limit, offset=offset)
        return jsonify({"runs": [serialize_run(r) for r in runs]})

