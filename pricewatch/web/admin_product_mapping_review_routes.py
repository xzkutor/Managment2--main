"""pricewatch.web.admin_product_mapping_review_routes — Product mapping review API.
Routes
------
GET  /api/product-mappings                   — confirmed-pairs listing with filters
GET  /api/comparison/eligible-target-products — manual picker candidates (scoped)
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from pricewatch.services.comparison_service import ComparisonService
from pricewatch.db.repositories import list_product_mappings_filtered
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import serialize_product_mapping_rich
logger = logging.getLogger(__name__)
def register_admin_product_mapping_review_routes(bp: Blueprint) -> None:
    """Register product mapping review routes on the shared blueprint."""
    @bp.route("/api/product-mappings", methods=["GET"])
    def api_product_mappings():
        """Return persisted product mappings with optional filters.
        Query params (all optional):
          status               — default "confirmed"; pass "rejected" or "" (all)
          reference_store_id   — int
          target_store_id      — int
          reference_category_id — int
          target_category_id   — int
          search               — substring on product names
          limit                — int, default 500
        """
        status_raw = request.args.get("status", "confirmed")
        status = status_raw if status_raw != "" else None
        def _int_or_none(key: str) -> int | None:
            v = request.args.get(key)
            try:
                return int(v) if v else None
            except (ValueError, TypeError):
                return None
        reference_store_id   = _int_or_none("reference_store_id")
        target_store_id      = _int_or_none("target_store_id")
        reference_category_id = _int_or_none("reference_category_id")
        target_category_id   = _int_or_none("target_category_id")
        search = request.args.get("search") or None
        limit_raw = _int_or_none("limit")
        limit = max(1, min(limit_raw or 500, 2000))
        session = get_db_session()()
        try:
            rows = list_product_mappings_filtered(
                session,
                reference_store_id=reference_store_id,
                target_store_id=target_store_id,
                reference_category_id=reference_category_id,
                target_category_id=target_category_id,
                status=status,
                search=search,
                limit=limit,
            )
        except Exception as exc:
            logger.exception("api_product_mappings failed: %s", exc)
            return jsonify({"error": "Internal server error"}), 500
        return jsonify({
            "product_mappings": [serialize_product_mapping_rich(r) for r in rows],
            "total": len(rows),
        })
    @bp.route("/api/comparison/eligible-target-products", methods=["GET"])
    def api_eligible_target_products():
        """Return products eligible for manual confirmation as a match.
        Query params:
          reference_product_id  — int (required)
          target_category_ids   — repeated or comma-joined ints (required)
          search                — optional substring
          limit                 — optional int, default 50
        """
        def _int_or_none(key: str) -> int | None:
            v = request.args.get(key)
            try:
                return int(v) if v else None
            except (ValueError, TypeError):
                return None
        ref_id = _int_or_none("reference_product_id")
        if not ref_id:
            return jsonify({"error": "reference_product_id is required"}), 400
        # Support ?target_category_ids=1&target_category_ids=2 or ?target_category_ids=1,2
        raw_ids = request.args.getlist("target_category_ids")
        target_category_ids: list[int] = []
        for part in raw_ids:
            for chunk in part.split(","):
                chunk = chunk.strip()
                if chunk:
                    try:
                        target_category_ids.append(int(chunk))
                    except ValueError:
                        pass
        if not target_category_ids:
            return jsonify({"error": "target_category_ids is required"}), 400
        search = request.args.get("search") or None
        limit_raw = _int_or_none("limit")
        limit = max(1, min(limit_raw or 50, 200))
        session = get_db_session()()
        try:
            svc = ComparisonService(session)
            items = svc.get_eligible_target_products(
                reference_product_id=ref_id,
                target_category_ids=target_category_ids,
                search=search,
                limit=limit,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            logger.exception("api_eligible_target_products failed: %s", exc)
            return jsonify({"error": "Internal server error"}), 500
        return jsonify({"products": items, "total": len(items)})
