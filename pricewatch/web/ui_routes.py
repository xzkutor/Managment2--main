"""pricewatch.web.ui_routes — UI page Blueprint.

Serves the SPA shell template for all operator-facing routes.

Route ownership (post Commit 10 cleanup)
-----------------------------------------
GET /          → spa.html  (Vue Router: ComparisonRouteView)
GET /service   → spa.html  (Vue Router: ServiceRouteView)
GET /gap       → spa.html  (Vue Router: GapRouteView)
GET /matches   → spa.html  (Vue Router: MatchesRouteView)
GET /app[/*]   → spa.html  (backward-compat alias)
404 fallback   → spa.html  for non-/api/ paths (history-mode deep-link
                            support); /api/* 404s pass through as JSON errors.

Flask remains the owner of /api/* — those routes are registered by
catalog_bp and admin_bp and are never intercepted by this blueprint.
405 (Method Not Allowed) responses from API routes are NOT affected
because the 404 handler fires only for paths with no registered route.
"""
from __future__ import annotations

import json as _json

from flask import Blueprint, render_template, current_app, jsonify, request

ui_bp = Blueprint("ui", __name__)


def _bootstrap_json() -> str:
    """Return a JSON-serialized ``window.__PRICEWATCH_BOOTSTRAP__`` payload.

    Normalizes all page-specific Flask config flags into one object so that
    every page shell and the SPA shell inject the same contract.
    Keep this payload small — runtime config only, no API data.
    """
    payload: dict = {
        "enableAdminSync": bool(current_app.config.get("ENABLE_ADMIN_SYNC", True)),
    }
    return _json.dumps(payload)


def _spa() -> str:
    """Render the SPA shell with the normalized bootstrap payload."""
    return render_template("spa.html", bootstrap_json=_bootstrap_json())


# ---------------------------------------------------------------------------
# Canonical operator UI routes — all serve the SPA shell (Commit 8 cutover)
# ---------------------------------------------------------------------------

@ui_bp.route("/")
def index():
    return _spa()


@ui_bp.route("/service")
def service_page():
    return _spa()


@ui_bp.route("/gap")
def gap_page():
    return _spa()


@ui_bp.route("/matches")
def matches_page():
    return _spa()


# ---------------------------------------------------------------------------
# Preview alias — kept for backward compatibility (Commit 5)
# ---------------------------------------------------------------------------

@ui_bp.route("/app", defaults={"subpath": ""})
@ui_bp.route("/app/<path:subpath>")
def spa_preview(subpath: str):
    """Backward-compat alias for bookmarked /app/* links.

    Canonical routes (/, /service, /gap, /matches) serve the SPA shell
    directly.  This alias is kept so that any existing bookmarks or external
    links to /app/* continue to work.
    """
    return _spa()


# ---------------------------------------------------------------------------
# SPA history-mode fallback via app-level 404 handler (Commit 8)
# ---------------------------------------------------------------------------

@ui_bp.app_errorhandler(404)
def _spa_404_fallback(e):
    """Serve the SPA shell for any unregistered non-API path (history mode).

    This fires only for paths that have NO registered Flask route at all.
    It does NOT interfere with 405 (Method Not Allowed) responses from routes
    that exist but reject the request method — those are returned normally.

    Split behaviour:
    - ``/api/*``  → pass through as a JSON 404 (API semantics preserved).
    - everything else → serve ``spa.html`` so Vue Router can render a
                        client-side 404 component or the correct route after
                        a deep-link / bookmark refresh.
    """
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found", "path": request.path}), 404
    return _spa(), 200


