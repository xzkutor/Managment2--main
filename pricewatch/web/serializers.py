"""pricewatch.web.serializers — Shared response serialization helpers.

All functions are *pure* (no DB session, no Flask context required).
They accept ORM model instances or service result objects and return
plain ``dict`` values ready for ``jsonify()``.

Datetime fields are always serialized as ISO-8601 strings (or ``None``).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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


def build_store_categories_payload(
    categories: list,
    product_counts: Optional[Dict[int, int]] = None,
) -> List[Dict[str, Any]]:
    """Build the standard category-list payload for a given list of categories.

    This is the single shared builder for category-list response construction.
    Both the canonical endpoint (``GET /api/stores/<store_id>/categories``) and
    the compatibility endpoint (``GET /api/categories``) must use this function
    to guarantee identical payload shape.

    Args:
        categories: list of Category ORM instances.
        product_counts: optional dict mapping ``category_id -> count``.
            Defaults to empty dict (all counts become 0).

    Returns:
        A list of serialized category dicts, each augmented with ``product_count``.
    """
    if product_counts is None:
        product_counts = {}
    return [
        dict(serialize_category(c), product_count=product_counts.get(c.id, 0))
        for c in categories
    ]


def serialize_run(run) -> Dict[str, Any]:
    return {
        "id": run.id,
        "store_id": run.store_id,
        "store": serialize_store(run.store) if getattr(run, "store", None) else None,
        "job_id": getattr(run, "job_id", None),
        "run_type": run.run_type,
        "trigger_type": getattr(run, "trigger_type", None),
        "status": run.status,
        "attempt": getattr(run, "attempt", 1),
        "queued_at": run.queued_at.isoformat() if getattr(run, "queued_at", None) else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "worker_id": getattr(run, "worker_id", None),
        "categories_processed": run.categories_processed,
        "products_processed": run.products_processed,
        "products_created": run.products_created,
        "products_updated": run.products_updated,
        "price_changes_detected": run.price_changes_detected,
        "error_message": run.error_message,
        "metadata_json": run.metadata_json,
        "checkpoint_out_json": getattr(run, "checkpoint_out_json", None),
        # Retry metadata (Decision 4 — RFC-008 addendum)
        "retryable": getattr(run, "retryable", False),
        "retry_of_run_id": getattr(run, "retry_of_run_id", None),
        "retry_exhausted": getattr(run, "retry_exhausted", False),
    }


def serialize_scrape_job(job) -> Dict[str, Any]:
    return {
        "id": job.id,
        "source_key": job.source_key,
        "runner_type": job.runner_type,
        "params_json": job.params_json,
        "enabled": job.enabled,
        "priority": job.priority,
        "allow_overlap": job.allow_overlap,
        "timeout_sec": job.timeout_sec,
        "max_retries": job.max_retries,
        "retry_backoff_sec": job.retry_backoff_sec,
        "concurrency_key": job.concurrency_key,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def serialize_scrape_schedule(schedule) -> Dict[str, Any]:
    return {
        "id": schedule.id,
        "job_id": schedule.job_id,
        "schedule_type": schedule.schedule_type,
        "cron_expr": schedule.cron_expr,
        "interval_sec": schedule.interval_sec,
        "timezone": schedule.timezone,
        "jitter_sec": schedule.jitter_sec,
        "misfire_policy": schedule.misfire_policy,
        "enabled": schedule.enabled,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
        "updated_at": schedule.updated_at.isoformat() if schedule.updated_at else None,
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
