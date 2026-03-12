"""pricewatch.web.adapter_routes — Supported internal/admin-facing adapter API Blueprint.

Status
------
These endpoints are **supported internal/admin-facing API**.
They are NOT part of the canonical DB-first catalog API.

Use cases:
- adapter/runtime introspection (inspect what categories an adapter fetches live);
- operational/admin debugging workflows;
- internal tooling that needs to verify adapter behaviour without a full sync.

Normal user-facing catalog/comparison/gap flows must use the DB-first catalog API
(``GET /api/stores``, ``GET /api/stores/<id>/categories``, etc.) rather than
depending on these adapter runtime routes.

URL paths are kept stable for backwards compatibility.

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


# ---------------------------------------------------------------------------
# Internal helper — adapter lookup
# ---------------------------------------------------------------------------

def _find_adapter(adapter_name: str):
    """Return the adapter matching *adapter_name*, or ``None`` if not found.

    Centralises adapter lookup so route handlers stay thin and the lookup
    logic is not duplicated.
    """
    _reg = get_registry()
    for a in _reg.adapters:
        if a.name == adapter_name:
            return a
    return None


def _adapter_not_found_response():
    """Return a standard JSON 404 response for an unknown adapter name."""
    return jsonify({"error": "adapter not found"}), 404


def _decode_category_names(cats: list) -> list:
    """Decode ``\\uXXXX`` escape sequences in category name fields in-place.

    Returns the same list for convenience.
    """
    for c in cats:
        if isinstance(c, dict) and "name" in c and isinstance(c["name"], str):
            c["name"] = decode_escapes(c["name"])
    return cats


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@adapter_bp.route("/api/adapters", methods=["GET"])
def adapters_list():
    """Return the list of available (non-reference) adapters and their domains.

    .. note::
        This is a **supported internal/admin-facing** endpoint.
        It is not part of the canonical DB-first catalog API.
        Normal UI flows do not depend on this endpoint.
    """
    _reg = get_registry()
    adapters = [
        {"name": a.name, "domains": a.domains}
        for a in _reg.adapters
        if not getattr(a, "is_reference", False)
    ]
    return jsonify({"adapters": adapters})


@adapter_bp.route("/api/adapters/<adapter_name>/categories", methods=["GET"])
def adapter_categories(adapter_name: str):
    """Fetch and return live categories from the named adapter.

    Triggers a live ``adapter.get_categories(default_client)`` call.
    Result is **not** persisted; this is an introspection/admin endpoint only.

    .. note::
        This is a **supported internal/admin-facing** endpoint.
        It is not part of the canonical DB-first catalog API.
        Normal UI flows must use ``GET /api/stores/<store_id>/categories``
        to read persisted, synced category data.

    Returns 404 if no adapter with the given name is registered.
    """
    adapter = _find_adapter(adapter_name)
    if adapter is None:
        return _adapter_not_found_response()
    logger.info("Fetching live categories for adapter: %s", adapter.name)
    cats = adapter.get_categories(default_client)
    if isinstance(cats, list):
        _decode_category_names(cats)
    return jsonify({"categories": cats})
