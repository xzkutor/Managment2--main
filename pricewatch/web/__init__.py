"""pricewatch.web — Flask web-layer package.

This package owns all HTTP-boundary code:
- Flask Blueprint modules (route handlers)
- web context / dependency helpers (pricewatch.web.context)
- shared response serialization helpers (pricewatch.web.serializers)

Blueprint registration is performed by ``app.py`` (the application
composition layer) via :func:`register_blueprints`.
"""
from __future__ import annotations

from flask import Flask


def register_blueprints(flask_app: Flask) -> None:
    """Register all web-layer blueprints onto *flask_app*."""
    from pricewatch.web.ui_routes import ui_bp
    from pricewatch.web.catalog_routes import catalog_bp
    from pricewatch.web.admin_routes import admin_bp
    from pricewatch.web.adapter_routes import adapter_bp

    flask_app.register_blueprint(ui_bp)
    flask_app.register_blueprint(catalog_bp)
    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(adapter_bp)

