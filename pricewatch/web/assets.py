"""pricewatch.web.assets — Flask ↔ Vite frontend asset integration.

Scope
-----
This module is the **only** Flask-side place that knows about:
- the Vite manifest file location
- the Vite dev server URL
- how to resolve hashed production asset paths
- how to construct <script>/<link> tags for Vue/Vite entries

Design rules
------------
- No dependency on scheduler, scraper, DB, or service code.
- No manifest loading at module import time (lazy, on first template use).
- The app continues to boot normally even when no frontend build exists.
- Manifest is cached per-process per unique path string (lru_cache).
- Templates call a single Jinja global: ``vite_asset_tags(entry_name)``.

Production manifest location
-----------------------------
Vite 5 writes ``<outDir>/.vite/manifest.json`` when ``manifest=True``.
The expected production path is::

    <project_root>/static/dist/.vite/manifest.json

That path is the default for ``VITE_MANIFEST_PATH`` config key.

Build entry
-----------
After the Commit 9 single-entry collapse, the only registered Vite entry
key is ``src/main.ts`` (key ``app`` in ``rollupOptions.input``, but Vite
uses the source file path as the manifest key).  ``spa.html`` references
this entry::

    {{ vite_asset_tags('src/main.ts') }}

Usage in Jinja templates
-------------------------
::

    {# emit all asset tags (CSS + JS) for the SPA entry #}
    {{ vite_asset_tags('src/main.ts') }}

Dev mode setup
--------------
Set in Flask config (or environment)::

    VITE_USE_DEV_SERVER=True
    VITE_DEV_SERVER_URL=http://localhost:5173
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from flask import Flask, current_app
from markupsafe import Markup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal — manifest loading
# ---------------------------------------------------------------------------

def _get_manifest_file_path(app: Flask) -> Path:
    """Return the resolved Path to the Vite manifest for *app*."""
    return Path(app.config["VITE_MANIFEST_PATH"])


@lru_cache(maxsize=8)
def _load_manifest_cached(path_str: str) -> dict:
    """Load and return the parsed Vite manifest keyed by *path_str*.

    The result is memoised per unique manifest path for the process lifetime.
    A ``FileNotFoundError`` with a clear human-readable message is raised when
    the file does not exist so that developers get actionable feedback instead
    of a raw Python traceback.
    """
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(
            f"[pricewatch] Vite manifest not found at '{path}'. "
            "Either run  npm run build  inside frontend/  to produce a "
            "production build, or set  VITE_USE_DEV_SERVER=True  for local "
            "development (no built files needed in that mode)."
        )
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    logger.debug("[pricewatch] Vite manifest loaded from %s (%d entries)", path, len(data))
    return data


def _load_manifest(app: Flask) -> dict:
    """Return the Vite manifest for *app*, using the per-process cache."""
    return _load_manifest_cached(str(_get_manifest_file_path(app)))


# ---------------------------------------------------------------------------
# Internal — URL construction
# ---------------------------------------------------------------------------

def _static_dist_url(app: Flask, asset_path: str) -> str:
    """Return the URL to serve *asset_path* from under ``static/dist/``.

    *asset_path* is the relative path within the dist directory as written
    by Vite in the manifest, e.g. ``assets/service-Duhh6EKS.js``.

    The URL prefix is taken from the ``FRONTEND_DIST_URL_PREFIX`` config key,
    defaulting to ``/static/dist``.  No request context is required.
    """
    prefix = app.config.get("FRONTEND_DIST_URL_PREFIX", "/static/dist").rstrip("/")
    return f"{prefix}/{asset_path}"


# ---------------------------------------------------------------------------
# Internal — tag builders
# ---------------------------------------------------------------------------

def _dev_tags(app: Flask, entry_name: str) -> Markup:
    """Emit Vite dev-server <script> tags for *entry_name*.

    Two tags are emitted:
    1. The Vite HMR client (``@vite/client``) — must come first.
    2. The entry module itself as a ``type="module"`` script.
    """
    base_url = app.config.get("VITE_DEV_SERVER_URL", "http://localhost:5173").rstrip("/")
    client_src = f"{base_url}/@vite/client"
    entry_src = f"{base_url}/{entry_name}"
    return Markup(
        f'\n<script type="module" src="{client_src}"></script>'
        f'\n<script type="module" src="{entry_src}"></script>\n'
    )


def _prod_tags(app: Flask, entry_name: str) -> Markup:
    """Emit hashed production <link>/<script> tags from the Vite manifest.

    CSS links are emitted before the script tag so the stylesheet is
    available before the module executes.

    When the manifest file is missing (e.g. during local development without
    a frontend build) returns empty Markup and logs a warning instead of
    raising, so the Flask page still renders without frontend assets.

    Raises
    ------
    KeyError
        If *entry_name* is not present in the manifest.  The error message
        lists available entry names to help diagnose typos.
    """
    try:
        manifest = _load_manifest(app)
    except FileNotFoundError as exc:
        logger.warning(
            "[pricewatch] %s — no frontend assets served for '%s'. "
            "Run  npm run build  inside frontend/  or set  VITE_USE_DEV_SERVER=True.",
            exc,
            entry_name,
        )
        return Markup("")

    if entry_name not in manifest:
        available = sorted(k for k, v in manifest.items() if v.get("isEntry"))
        raise KeyError(
            f"[pricewatch] Vite entry '{entry_name}' not found in manifest. "
            f"Available entry keys: {available}"
        )

    entry = manifest[entry_name]
    parts: list[str] = []

    # CSS assets — emit <link> tags in manifest order before the JS module
    for css_asset in entry.get("css", []):
        href = _static_dist_url(app, css_asset)
        parts.append(f'<link rel="stylesheet" href="{href}">')

    # Primary JS module
    js_url = _static_dist_url(app, entry["file"])
    parts.append(f'<script type="module" src="{js_url}"></script>')

    return Markup("\n".join(parts))


# ---------------------------------------------------------------------------
# Public Jinja helper
# ---------------------------------------------------------------------------

def vite_asset_tags(entry_name: str) -> Markup:
    """Return safe Markup containing all asset tags for a Vite entry.

    Selects dev-server or production mode based on the ``VITE_USE_DEV_SERVER``
    Flask config flag (default: ``False``).

    Parameters
    ----------
    entry_name:
        The Vite entry key as declared in ``frontend/vite.config.ts``.
        In production mode this must match a key in the manifest file,
        e.g. ``'src/main.ts'``.

    Returns
    -------
    markupsafe.Markup
        Safe HTML string containing ``<link>`` and/or ``<script>`` tags.
        Can be rendered directly in Jinja: ``{{ vite_asset_tags(...) }}``.

    Raises
    ------
    KeyError
        Entry name not found in manifest (production mode only).
    FileNotFoundError
        Manifest file missing (production mode only).

    Examples
    --------
    In a Jinja template, just before ``</body>``::

        {{ vite_asset_tags('src/main.ts') }}
    """
    app = current_app._get_current_object()  # type: ignore[attr-defined]

    if app.config.get("VITE_USE_DEV_SERVER", False):
        return _dev_tags(app, entry_name)
    return _prod_tags(app, entry_name)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_asset_helpers(app: Flask) -> None:
    """Register ``vite_asset_tags`` as a Jinja global on *app*.

    This is purely additive and has no side effects — no manifest is loaded
    here, no filesystem is touched.  Calling this multiple times is safe
    (subsequent calls are no-ops for the same app instance).

    Called from ``pricewatch.app_factory.create_app()`` after blueprint
    registration.
    """
    app.jinja_env.globals.setdefault("vite_asset_tags", vite_asset_tags)
    logger.debug("[pricewatch] vite_asset_tags registered as Jinja2 global")

