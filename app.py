"""app.py — Application composition and bootstrap layer.

Responsibilities
----------------
- Application factory :func:`create_app`
- Flask / CORS configuration
- DB engine + session wiring (per-app-instance, not global)
- App-context teardown
- Bootstrap store-registry sync at startup
- Blueprint registration (routes live in ``pricewatch/web/``)
- App-level ``after_request`` hook (charset enforcement)

All route handlers and serialization helpers have been moved into the
``pricewatch.web`` package.  See ``pricewatch/web/__init__.py`` for the
blueprint registration entry-point.

Runtime entry-point: ``app = create_app()`` below.
"""
from flask import Flask
from flask_cors import CORS

import logging

from pricewatch.core.registry import get_registry
from pricewatch.db import Base, init_engine, init_db, get_session_factory, get_scoped_session
from pricewatch.services.store_service import StoreService
from pricewatch.web import register_blueprints

logger = logging.getLogger(__name__)


def create_app(config_override=None):
    """Application factory.

    Parameters
    ----------
    config_override:
        Optional dict of Flask/app config values applied *before* DB
        initialisation.  Pass ``{"DATABASE_URL": "sqlite:///:memory:",
        "TESTING": True}`` to point the app at a test database.

    Returns
    -------
    Flask
        A fully configured Flask application instance with its own DB wiring.
    """
    flask_app = Flask(__name__)
    CORS(flask_app)
    flask_app.config.setdefault("ENABLE_ADMIN_SYNC", True)
    flask_app.json.ensure_ascii = False

    if config_override:
        flask_app.config.update(config_override)

    # --- DB wiring (per-app instance, not global) ---
    _engine = init_engine(flask_app.config)
    _factory = get_session_factory(_engine)
    _scoped = get_scoped_session(_factory)
    init_db(_engine, base=Base, app_config=flask_app.config)

    flask_app.extensions["db_engine"] = _engine
    flask_app.extensions["db_session_factory"] = _factory
    flask_app.extensions["db_scoped_session"] = _scoped

    @flask_app.teardown_appcontext
    def shutdown_session(exception=None):  # noqa: F811
        flask_app.extensions["db_scoped_session"].remove()

    # Bootstrap store registry only in non-test mode
    if not flask_app.config.get("TESTING"):
        _reg = get_registry()
        with flask_app.app_context():
            _sess = _scoped()
            _svc = StoreService(_sess)
            try:
                _svc.sync_with_registry(_reg)
                _sess.commit()
            except Exception as exc:  # pragma: no cover
                _sess.rollback()
                logger.exception("Failed to bootstrap stores: %s", exc)
            finally:
                _scoped.remove()

    # --- App-level after_request hook (must stay here per architecture decision) ---
    @flask_app.after_request
    def set_response_charset(response):
        """Ensure responses include charset=utf-8 in Content-Type."""
        try:
            content_type = response.headers.get("Content-Type", "")
            if "charset" not in content_type.lower():
                mimetype = response.mimetype or ""
                if mimetype in ("application/json", "text/html", "application/javascript"):
                    response.headers["Content-Type"] = f"{mimetype}; charset=utf-8"
        except Exception:
            logger.exception("set_response_charset failed")
        return response

    # --- Blueprint registration ---
    register_blueprints(flask_app)

    return flask_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)

