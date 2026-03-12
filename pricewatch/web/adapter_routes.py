"""pricewatch.web.adapter_routes — Adapter-facing API Blueprint.

Isolates adapter-listing and adapter-category endpoints from the main
DB-first API surface.  The same public URLs are preserved; this commit
is purely a structural isolation.

Routes
------
GET /api/adapters
GET /api/adapters/<adapter_name>/categories
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from pricewatch.core.registry import get_registry
from pricewatch.net.http_client import default_client
from pricewatch.web.serializers import decode_escapes

logger = logging.getLogger(__name__)

adapter_bp = Blueprint("adapters", __name__)


@adapter_bp.route("/api/adapters", methods=["GET"])
def adapters_list():
    """Return the list of available adapters and their supported domains."""
    _reg = get_registry()
    adapters = []
    for adapter in _reg.adapters:
        if getattr(adapter, "is_reference", False):
            continue
        adapters.append({"name": adapter.name, "domains": adapter.domains})
    return jsonify({"adapters": adapters})


@adapter_bp.route("/api/adapters/<adapter_name>/categories", methods=["GET"])
def adapter_categories(adapter_name: str):
    """Return categories produced by the named adapter (by adapter.name)."""
    _reg = get_registry()
    adapter = None
    for a in _reg.adapters:
        if a.name == adapter_name:
            adapter = a
            break
    if not adapter:
        return jsonify({"error": "adapter not found"}), 404
    logger.info("Fetching categories for adapter: %s", adapter.name)
    cats = adapter.get_categories(default_client)
    if isinstance(cats, list):
        for c in cats:
            if isinstance(c, dict) and "name" in c and isinstance(c["name"], str):
                c["name"] = decode_escapes(c["name"])
    return jsonify({"categories": cats})

