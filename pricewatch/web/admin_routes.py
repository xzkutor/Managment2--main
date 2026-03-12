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
from pricewatch.db.repositories import create_product_mapping
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
    store_id = request.args.get("store_id", type=int)
    run_type = request.args.get("run_type")
    status = request.args.get("status")
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", type=int)
    service = ScrapeHistoryService(session)
    runs = service.list_runs(
        store_id=store_id, run_type=run_type, status=status,
        limit=limit, offset=offset,
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
    return jsonify({"runs": [serialize_run(r) for r in runs]})


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

