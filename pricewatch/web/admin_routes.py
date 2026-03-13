"""pricewatch.web.admin_routes — Admin / service-oriented API Blueprint.

Handles admin operations, sync flows, mappings, comparison, gap, and
scrape-history endpoints.

Routes
------
POST /api/admin/stores/sync
POST /api/stores/<store_id>/categories/sync
POST /api/categories/<category_id>/products/sync
POST /api/category-mappings/auto-link
GET  /api/category-mappings
POST /api/category-mappings
PUT  /api/category-mappings/<mapping_id>
DELETE /api/category-mappings/<mapping_id>
GET  /api/scrape-runs
GET  /api/scrape-runs/<run_id>
GET  /api/scrape-status
POST /api/comparison
POST /api/comparison/confirm-match
POST /api/gap
POST /api/gap/status
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, current_app

from pricewatch.core.registry import get_registry
from pricewatch.db.repositories import (
    create_product_mapping,
    create_scrape_job,
    get_scrape_job,
    list_scrape_jobs,
    update_scrape_job,
    enqueue_run,
    list_runs_for_job,
    create_scrape_schedule,
    get_schedule_for_job,
    list_schedules_for_job,
    update_scrape_schedule,
    has_active_run_for_job,
)
from pricewatch.services.category_sync_service import CategorySyncService
from pricewatch.services.product_sync_service import ProductSyncService
from pricewatch.services.mapping_service import MappingService
from pricewatch.services.scrape_history_service import ScrapeHistoryService
from pricewatch.services.store_service import StoreService
from pricewatch.services.comparison_service import ComparisonService
from pricewatch.services.category_matching_service import CategoryMatchingService
from pricewatch.services.gap_service import GapService
from pricewatch.schemas.validation import parse_request_body
from pricewatch.schemas.requests.comparison import ComparisonRequest, ConfirmMatchRequest
from pricewatch.schemas.requests.gap import GapRequest, GapStatusRequest
from pricewatch.schemas.requests.mappings import (
    AutoLinkCategoryMappingsRequest,
    CreateCategoryMappingRequest,
    UpdateCategoryMappingRequest,
)
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import (
    serialize_store,
    serialize_category,
    serialize_product,
    serialize_mapping,
    mapping_list_payload,
    serialize_run,
    serialize_product_mapping,
    serialize_scrape_job,
    serialize_scrape_schedule,
)

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------------------
# Store admin
# ---------------------------------------------------------------------------

@admin_bp.route("/api/admin/stores/sync", methods=["POST"])
def api_admin_sync_stores():
    if not current_app.config.get("ENABLE_ADMIN_SYNC", True):
        return jsonify({"error": "not found"}), 404
    _reg = get_registry()
    session = get_db_session()()
    service = StoreService(session)
    try:
        stores = service.sync_with_registry(_reg)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("Admin store sync failed: %s", exc)
        return jsonify({"error": str(exc)}), 500
    return jsonify({"stores": [serialize_store(s) for s in stores]})


# ---------------------------------------------------------------------------
# Category / product sync
# ---------------------------------------------------------------------------

@admin_bp.route("/api/stores/<int:store_id>/categories/sync", methods=["POST"])
def api_sync_categories(store_id: int):
    session = get_db_session()()
    service = CategorySyncService(session)
    try:
        result = service.sync_store_categories(store_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "success": True,
        "store": serialize_store(result["store"]),
        "scrape_run": serialize_run(result["scrape_run"]),
        "categories": [serialize_category(c) for c in result["categories"]],
    })


@admin_bp.route("/api/categories/<int:category_id>/products/sync", methods=["POST"])
def api_sync_category_products(category_id: int):
    session = get_db_session()()
    service = ProductSyncService(session)
    try:
        result = service.sync_category_products(category_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "success": True,
        "category": serialize_category(result["category"]),
        "store": serialize_store(result["store"]),
        "scrape_run": serialize_run(result["scrape_run"]),
        "summary": result["summary"],
        "products": [serialize_product(p) for p in result["products"]],
    })


# ---------------------------------------------------------------------------
# Category mappings
# ---------------------------------------------------------------------------

@admin_bp.route("/api/category-mappings/auto-link", methods=["POST"])
def api_auto_link_category_mappings():
    """Auto-create category mappings by exact normalized_name match."""
    payload, err = parse_request_body(AutoLinkCategoryMappingsRequest)
    if err:
        return err
    session = get_db_session()()
    try:
        result = CategoryMatchingService.auto_link(
            session,
            reference_store_id=payload.reference_store_id,
            target_store_id=payload.target_store_id,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        session.rollback()
        logger.exception("auto_link_category_mappings failed: %s", exc)
        return jsonify({"error": "Internal server error"}), 500
    return jsonify(result)


@admin_bp.route("/api/category-mappings", methods=["GET"])
def api_list_category_mappings():
    session = get_db_session()()
    reference_store_id = request.args.get("reference_store_id", type=int)
    target_store_id = request.args.get("target_store_id", type=int)
    service = MappingService(session)
    return jsonify(mapping_list_payload(service, reference_store_id, target_store_id))


@admin_bp.route("/api/category-mappings", methods=["POST"])
def api_create_category_mapping():
    payload, err = parse_request_body(CreateCategoryMappingRequest)
    if err:
        return err
    session = get_db_session()()
    service = MappingService(session)
    try:
        mapping = service.create_category_mapping(
            reference_category_id=payload.reference_category_id,
            target_category_id=payload.target_category_id,
            match_type=payload.match_type,
            confidence=payload.confidence,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400
    reference_store_id = request.args.get("reference_store_id", type=int)
    target_store_id = request.args.get("target_store_id", type=int)
    response_payload = dict(mapping_list_payload(service, reference_store_id, target_store_id))
    response_payload["mapping"] = serialize_mapping(mapping)
    return jsonify(response_payload)


@admin_bp.route("/api/category-mappings/<int:mapping_id>", methods=["PUT"])
def api_update_category_mapping(mapping_id: int):
    payload, err = parse_request_body(UpdateCategoryMappingRequest)
    if err:
        return err
    session = get_db_session()()
    service = MappingService(session)
    try:
        mapping = service.update_category_mapping(
            mapping_id,
            match_type=payload.match_type,
            confidence=payload.confidence,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400
    reference_store_id = request.args.get("reference_store_id", type=int)
    target_store_id = request.args.get("target_store_id", type=int)
    response_payload = dict(mapping_list_payload(service, reference_store_id, target_store_id))
    response_payload["mapping"] = serialize_mapping(mapping)
    return jsonify(response_payload)


@admin_bp.route("/api/category-mappings/<int:mapping_id>", methods=["DELETE"])
def api_delete_category_mapping(mapping_id: int):
    session = get_db_session()()
    service = MappingService(session)
    try:
        service.delete_category_mapping(mapping_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400
    reference_store_id = request.args.get("reference_store_id", type=int)
    target_store_id = request.args.get("target_store_id", type=int)
    response_payload = dict(mapping_list_payload(service, reference_store_id, target_store_id))
    response_payload.update({"deleted": True, "mapping_id": mapping_id})
    return jsonify(response_payload)


# ---------------------------------------------------------------------------
# Scrape history / status
# ---------------------------------------------------------------------------

@admin_bp.route("/api/scrape-runs", methods=["GET"])
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


@admin_bp.route("/api/scrape-runs/<int:run_id>", methods=["GET"])
def api_get_run(run_id: int):
    session = get_db_session()()
    service = ScrapeHistoryService(session)
    try:
        run = service.get_run(run_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"run": serialize_run(run)})


@admin_bp.route("/api/scrape-status", methods=["GET"])
def api_scrape_status():
    session = get_db_session()()
    store_id = request.args.get("store_id", type=int)
    run_type = request.args.get("run_type")
    status = request.args.get("status") or "running"
    limit = request.args.get("limit", type=int) or 5
    service = ScrapeHistoryService(session)
    runs = service.list_runs(
        store_id=store_id, run_type=run_type, status=status, limit=limit
    )

    # Scheduler runtime observability (Commit 6)
    import os  # noqa: PLC0415
    from pricewatch.scrape.bootstrap import get_scheduler_runtime_status  # noqa: PLC0415

    def _cfg_bool(key: str, default: bool) -> bool:
        val = current_app.config.get(key, os.environ.get(key))
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in ("1", "true", "yes", "on")

    scheduler_status = get_scheduler_runtime_status()
    scheduler_status["scheduler_enabled"]   = _cfg_bool("SCHEDULER_ENABLED",   True)
    scheduler_status["scheduler_autostart"] = _cfg_bool("SCHEDULER_AUTOSTART", True)

    return jsonify({
        "runs": [serialize_run(r) for r in runs],
        "scheduler": scheduler_status,
    })


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@admin_bp.route("/api/comparison/confirm-match", methods=["POST"])
def api_comparison_confirm_match():
    """Persist a confirmed product match into product_mappings."""
    payload, err = parse_request_body(ConfirmMatchRequest)
    if err:
        return err
    session = get_db_session()()
    try:
        pm = create_product_mapping(
            session,
            reference_product_id=payload.reference_product_id,
            target_product_id=payload.target_product_id,
            match_status=payload.match_status or "confirmed",
            confidence=payload.confidence,
            comment=payload.comment,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("confirm-match failed: %s", exc)
        return jsonify({"error": str(exc)}), 400
    return jsonify({"product_mapping": serialize_product_mapping(pm)})


@admin_bp.route("/api/comparison", methods=["POST"])
def api_comparison():
    """Compare products from a reference category against mapped target categories."""
    payload, err = parse_request_body(ComparisonRequest)
    if err:
        return err
    session = get_db_session()()
    try:
        svc_kwargs: dict = {"reference_category_id": payload.reference_category_id}
        if payload.target_category_ids is not None:
            svc_kwargs["target_category_ids"] = payload.target_category_ids
        elif payload.target_category_id is not None:
            svc_kwargs["target_category_id"] = payload.target_category_id
        if payload.target_store_id is not None:
            svc_kwargs["target_store_id"] = payload.target_store_id
        result = ComparisonService(session).compare(**svc_kwargs)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("api_comparison failed: %s", exc)
        return jsonify({"error": "Internal server error"}), 500
    return jsonify(result)


# ---------------------------------------------------------------------------
# Gap
# ---------------------------------------------------------------------------

@admin_bp.route("/api/gap", methods=["POST"])
def api_gap():
    """Return grouped target-only (gap) items for a reference category + target categories."""
    payload, err = parse_request_body(GapRequest)
    if err:
        return err
    session = get_db_session()()
    try:
        result = GapService(session).build_gap_view(
            target_store_id=payload.target_store_id,
            reference_category_id=payload.reference_category_id,
            target_category_ids=payload.target_category_ids,
            search=payload.search,
            only_available=payload.only_available,
            statuses=payload.statuses,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("api_gap failed: %s", exc)
        return jsonify({"error": "Internal server error"}), 500
    return jsonify(result)


@admin_bp.route("/api/gap/status", methods=["POST"])
def api_gap_status():
    """Persist a gap item review status (in_progress or done)."""
    payload, err = parse_request_body(GapStatusRequest)
    if err:
        return err
    session = get_db_session()()
    try:
        result = GapService(session).set_gap_item_status(
            reference_category_id=payload.reference_category_id,
            target_product_id=payload.target_product_id,
            status=payload.status,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        session.rollback()
        logger.exception("api_gap_status failed: %s", exc)
        return jsonify({"error": "Internal server error"}), 500
    return jsonify({"success": True, "item": result})


# ---------------------------------------------------------------------------
# Scheduler control-plane — Jobs
# ---------------------------------------------------------------------------

@admin_bp.route("/api/admin/scrape/jobs", methods=["GET"])
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


@admin_bp.route("/api/admin/scrape/jobs", methods=["POST"])
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

    payload: dict = {"job": serialize_scrape_job(job)}
    if schedule is not None:
        payload["schedule"] = serialize_scrape_schedule(schedule)
    return jsonify(payload), 201


@admin_bp.route("/api/admin/scrape/jobs/<int:job_id>", methods=["GET"])
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


@admin_bp.route("/api/admin/scrape/jobs/<int:job_id>", methods=["PATCH"])
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


@admin_bp.route("/api/admin/scrape/jobs/<int:job_id>/run", methods=["POST"])
def api_manual_enqueue_job(job_id: int):
    """Manually enqueue a run for a job (uses same queued-run model as scheduler).

    Overlap policy (Decision 2 — RFC-008 addendum):
      If job.allow_overlap is False and an active run already exists,
      returns 409 Conflict.
    """
    session = get_db_session()()
    job = get_scrape_job(session, job_id)
    if not job:
        return jsonify({"error": f"ScrapeJob {job_id} not found"}), 404

    # Overlap guard — Decision 2
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


@admin_bp.route("/api/admin/scrape/jobs/<int:job_id>/runs", methods=["GET"])
def api_list_runs_for_job(job_id: int):
    session = get_db_session()()
    status = request.args.get("status")
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", type=int)
    runs = list_runs_for_job(session, job_id, status=status, limit=limit, offset=offset)
    return jsonify({"runs": [serialize_run(r) for r in runs]})


# ---------------------------------------------------------------------------
# Scheduler control-plane — Schedules
# ---------------------------------------------------------------------------

@admin_bp.route("/api/admin/scrape/jobs/<int:job_id>/schedule", methods=["GET"])
def api_get_job_schedule(job_id: int):
    session = get_db_session()()
    schedules = list_schedules_for_job(session, job_id)
    return jsonify({"schedules": [serialize_scrape_schedule(s) for s in schedules]})


@admin_bp.route("/api/admin/scrape/jobs/<int:job_id>/schedule", methods=["PUT"])
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



