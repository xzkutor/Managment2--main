"""pricewatch.web.serializers — Shared response serialization helpers.

All functions are *pure* (no DB session, no Flask context required).
They accept ORM model instances or service result objects and return
plain ``dict`` values ready for ``jsonify()``.

Datetime fields are always serialized as ISO-8601 strings (or ``None``).
"""
from __future__ import annotations

from typing import Any, Dict

from pricewatch.core.normalize import parse_price_value
from pricewatch.db.models import ProductMapping


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def decode_escapes(s: str) -> str:
    """Decode ``\\uXXXX`` escape sequences in *s* when present.

    Only attempts decoding when the string literally contains the two-character
    sequence ``\\u`` (i.e. looks like it might hold escaped unicode).  Returns
    *s* unchanged on any decoding error.
    """
    if not isinstance(s, str) or "\\u" not in s:
        return s
    try:
        return s.encode("utf-8").decode("unicode_escape")
    except Exception:
        return s


def reference_item_to_dict(item) -> Dict[str, Any]:
    """Serialize a reference-catalog item to a plain dict."""
    price_value, currency = parse_price_value(item.price_raw)
    return {
        "name": item.name,
        "price": price_value,
        "currency": currency,
        "url": item.url,
        "source_site": item.source_site,
        "price_raw": item.price_raw,
    }


# ---------------------------------------------------------------------------
# ORM model serializers
# ---------------------------------------------------------------------------

def serialize_store(store) -> Dict[str, Any]:
    return {
        "id": store.id,
        "name": store.name,
        "is_reference": store.is_reference,
        "base_url": store.base_url,
    }


def serialize_category(cat) -> Dict[str, Any]:
    return {
        "id": cat.id,
        "store_id": cat.store_id,
        "name": cat.name,
        "normalized_name": cat.normalized_name,
        "url": cat.url,
        "external_id": cat.external_id,
        "updated_at": cat.updated_at.isoformat() if cat.updated_at else None,
    }


def serialize_product(prod) -> Dict[str, Any]:
    return {
        "id": prod.id,
        "store_id": prod.store_id,
        "category_id": prod.category_id,
        "name": prod.name,
        "normalized_name": prod.normalized_name,
        "name_hash": prod.name_hash,
        "price": prod.price,
        "currency": prod.currency,
        "product_url": prod.product_url,
        "source_url": prod.source_url,
        "is_available": prod.is_available,
        "scraped_at": prod.scraped_at.isoformat() if prod.scraped_at else None,
        "updated_at": prod.updated_at.isoformat() if prod.updated_at else None,
    }


def serialize_mapping(mapping) -> Dict[str, Any]:
    ref_cat = getattr(mapping, "reference_category", None)
    tgt_cat = getattr(mapping, "target_category", None)
    ref_store = getattr(ref_cat, "store", None) if ref_cat else None
    tgt_store = getattr(tgt_cat, "store", None) if tgt_cat else None
    return {
        "id": mapping.id,
        "reference_category_id": getattr(mapping, "reference_category_id", None),
        "target_category_id": getattr(mapping, "target_category_id", None),
        "reference_category_name": getattr(ref_cat, "name", None),
        "target_category_name": getattr(tgt_cat, "name", None),
        "reference_store_id": getattr(ref_store, "id", None) or getattr(ref_cat, "store_id", None),
        "target_store_id": getattr(tgt_store, "id", None) or getattr(tgt_cat, "store_id", None),
        "reference_store_name": getattr(ref_store, "name", None),
        "target_store_name": getattr(tgt_store, "name", None),
        "match_type": getattr(mapping, "match_type", None),
        "confidence": getattr(mapping, "confidence", None),
        "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
    }


def mapping_list_payload(service, reference_store_id, target_store_id) -> Dict[str, Any]:
    """Build the standard list-mappings response payload."""
    return {
        "mappings": [
            serialize_mapping(m)
            for m in service.list_category_mappings(
                reference_store_id=reference_store_id,
                target_store_id=target_store_id,
            )
        ],
    }


def serialize_run(run) -> Dict[str, Any]:
    return {
        "id": run.id,
        "store_id": run.store_id,
        "store": serialize_store(run.store) if getattr(run, "store", None) else None,
        "run_type": run.run_type,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "categories_processed": run.categories_processed,
        "products_processed": run.products_processed,
        "products_created": run.products_created,
        "products_updated": run.products_updated,
        "price_changes_detected": run.price_changes_detected,
        "error_message": run.error_message,
        "metadata_json": run.metadata_json,
    }


def serialize_product_mapping(pm: ProductMapping) -> Dict[str, Any]:
    ref = getattr(pm, "reference_product", None)
    tgt = getattr(pm, "target_product", None)
    return {
        "id": pm.id,
        "reference_product_id": pm.reference_product_id,
        "target_product_id": pm.target_product_id,
        "reference_product": serialize_product(ref) if ref else None,
        "target_product": serialize_product(tgt) if tgt else None,
        "match_status": pm.match_status,
        "confidence": pm.confidence,
        "comment": pm.comment,
        "updated_at": pm.updated_at.isoformat() if pm.updated_at else None,
    }

