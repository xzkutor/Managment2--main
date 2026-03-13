"""pricewatch.web.admin_store_sync_routes -- Store and manual sync routes.

Routes
------
POST /api/admin/stores/sync
POST /api/stores/<store_id>/categories/sync
POST /api/categories/<category_id>/products/sync
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, current_app

from pricewatch.core.registry import get_registry
from pricewatch.services.category_sync_service import CategorySyncService
from pricewatch.services.product_sync_service import ProductSyncService
from pricewatch.services.store_service import StoreService
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import (
    serialize_store,
    serialize_category,
    serialize_product,
    serialize_run,
)

logger = logging.getLogger(__name__)


def register_admin_store_sync_routes(bp: Blueprint) -> None:
    """Register store and manual sync routes on the shared blueprint."""

    @bp.route("/api/admin/stores/sync", methods=["POST"])
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

    @bp.route("/api/stores/<int:store_id>/categories/sync", methods=["POST"])
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

    @bp.route("/api/categories/<int:category_id>/products/sync", methods=["POST"])
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

