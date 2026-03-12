"""pricewatch.web.catalog_routes — DB-first catalog read-only API Blueprint.

Serves read-oriented catalog endpoints backed directly by the DB.

Routes
------
GET /api/stores
GET /api/categories                              (cleanup candidate — later wave)
GET /api/stores/<store_id>/categories
GET /api/categories/<category_id>/products
GET /api/categories/<reference_category_id>/mapped-target-categories
"""
from __future__ import annotations

import logging
from typing import cast

from flask import Blueprint, jsonify, request

from pricewatch.db.repositories import list_stores, list_categories_by_store, list_products_by_category
from pricewatch.db.repositories.category_repository import list_mapped_target_categories
from pricewatch.db.models import Store
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import (
    serialize_store,
    serialize_category,
    serialize_product,
)

logger = logging.getLogger(__name__)

catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.route("/api/stores", methods=["GET"])
def api_list_stores():
    session = get_db_session()()
    stores = list_stores(session)
    return jsonify({"stores": [serialize_store(s) for s in stores]})


# TODO(cleanup): GET /api/categories is a cleanup candidate for a later wave.
#   It currently returns the reference store's categories without a store_id
#   in the path, which is inconsistent with /api/stores/<id>/categories.
#   Do not redesign it in this wave.
@catalog_bp.route("/api/categories", methods=["GET"])
def categories_list():
    """Return categories for the reference store from DB (no scraping)."""
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
            from pricewatch.db.repositories.category_repository import count_products_by_category
            product_counts = count_products_by_category(session, store_id_value)
        except Exception:
            product_counts = {}
    return jsonify({
        "store": serialize_store(ref_store) if ref_store else None,
        "categories": [
            dict(serialize_category(c), product_count=product_counts.get(c.id, 0))
            for c in categories
        ],
    })


@catalog_bp.route("/api/stores/<int:store_id>/categories", methods=["GET"])
def api_list_store_categories(store_id: int):
    session = get_db_session()()
    cats = list_categories_by_store(session, store_id)
    try:
        from pricewatch.db.repositories.category_repository import count_products_by_category
        product_counts = count_products_by_category(session, store_id)
    except Exception:
        product_counts = {}
    return jsonify({
        "categories": [
            dict(serialize_category(c), product_count=product_counts.get(c.id, 0))
            for c in cats
        ],
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

