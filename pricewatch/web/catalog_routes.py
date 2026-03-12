"""pricewatch.web.catalog_routes — DB-first catalog read-only API Blueprint.

Serves read-oriented catalog endpoints backed directly by the DB.

Routes
------
GET /api/stores
GET /api/stores/<store_id>/categories            (canonical)
GET /api/categories                              (compatibility — migration target, do not add new consumers)
GET /api/categories/<category_id>/products
GET /api/categories/<reference_category_id>/mapped-target-categories
"""
from __future__ import annotations

import logging
from typing import cast

from flask import Blueprint, jsonify, request

from pricewatch.db.repositories import list_stores, list_categories_by_store, list_products_by_category
from pricewatch.db.repositories.category_repository import list_mapped_target_categories, count_products_by_category
from pricewatch.db.models import Store
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import (
    serialize_store,
    serialize_category,
    serialize_product,
    build_store_categories_payload,
)

logger = logging.getLogger(__name__)

catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.route("/api/stores", methods=["GET"])
def api_list_stores():
    session = get_db_session()()
    stores = list_stores(session)
    return jsonify({"stores": [serialize_store(s) for s in stores]})


# ---------------------------------------------------------------------------
# Compatibility endpoint — migration target.
#
# GET /api/categories returns the reference store's categories without a
# store_id in the path.  This endpoint is intentionally left operational for
# backwards compatibility but is a MIGRATION TARGET for eventual deprecation
# after all internal consumers are moved to the canonical endpoint below.
#
# Do NOT add new consumers of this endpoint.
# Canonical replacement: GET /api/stores/<store_id>/categories
# ---------------------------------------------------------------------------
@catalog_bp.route("/api/categories", methods=["GET"])
def categories_list():
    """Return categories for the reference store from DB (no scraping).

    .. deprecated::
        Compatibility endpoint.  Use ``GET /api/stores/<store_id>/categories``
        instead.  This endpoint resolves the reference store implicitly and
        will be formally deprecated once all internal consumers are migrated.
    """
    session = get_db_session()()
    ref_store = session.query(Store).filter(Store.is_reference.is_(True)).first()
    if ref_store is None:
        stores = list_stores(session)
        ref_store = next((s for s in stores if getattr(s, "is_reference", False)), None)
    if ref_store is None:
        stores = list_stores(session)
        ref_store = stores[0] if stores else None
    store_id_value = cast(int, cast(object, ref_store.id)) if ref_store is not None else None
    categories = list_categories_by_store(session, store_id_value) if store_id_value is not None else []
    product_counts: dict = {}
    if store_id_value is not None:
        try:
            product_counts = count_products_by_category(session, store_id_value)
        except Exception:
            product_counts = {}
    return jsonify({
        "store": serialize_store(ref_store) if ref_store else None,
        "categories": build_store_categories_payload(categories, product_counts),
    }), 200, {
        "Deprecation": "true",
        "Link": '</api/stores/{store_id}/categories>; rel="successor-version"',
        "Sunset": "TBD — after internal consumer migration is complete",
    }


# ---------------------------------------------------------------------------
# Canonical store-scoped categories endpoint.
# ---------------------------------------------------------------------------
@catalog_bp.route("/api/stores/<int:store_id>/categories", methods=["GET"])
def api_list_store_categories(store_id: int):
    """Return categories for a specific store from DB.

    This is the **canonical** categories endpoint.  All internal consumers
    should use this form with an explicit ``store_id``.
    """
    session = get_db_session()()
    cats = list_categories_by_store(session, store_id)
    try:
        product_counts = count_products_by_category(session, store_id)
    except Exception:
        product_counts = {}
    return jsonify({
        "categories": build_store_categories_payload(cats, product_counts),
    })


@catalog_bp.route("/api/categories/<int:category_id>/products", methods=["GET"])
def api_list_category_products(category_id: int):
    session = get_db_session()()
    products = list_products_by_category(session, category_id)
    return jsonify({"products": [serialize_product(p) for p in products]})


@catalog_bp.route(
    "/api/categories/<int:reference_category_id>/mapped-target-categories",
    methods=["GET"],
)
def api_mapped_target_categories(reference_category_id: int):
    """Return all target categories mapped to the given reference category.

    Optional query param: ``?target_store_id=<id>`` to filter by target store.
    """
    session = get_db_session()()
    target_store_id = request.args.get("target_store_id", type=int)
    from pricewatch.db.models import Category as _Category
    ref_cat = session.get(_Category, reference_category_id)
    mappings = list_mapped_target_categories(
        session, reference_category_id, target_store_id=target_store_id
    )
    result = []
    target_store_meta = None
    for m in mappings:
        tgt = getattr(m, "target_category", None)
        if tgt is None:
            continue
        tgt_store = getattr(tgt, "store", None)
        if target_store_meta is None and tgt_store is not None:
            target_store_meta = serialize_store(tgt_store)
        result.append({
            "target_category_id": tgt.id,
            "target_category_name": tgt.name,
            "target_store_id": tgt.store_id,
            "target_store_name": getattr(tgt_store, "name", None),
            "match_type": m.match_type,
            "confidence": m.confidence,
            "mapping_id": m.id,
        })
    return jsonify({
        "reference_category": serialize_category(ref_cat) if ref_cat else {"id": reference_category_id},
        "target_store": target_store_meta,
        "mapped_target_categories": result,
    })

