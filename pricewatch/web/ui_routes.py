"""pricewatch.web.ui_routes — UI page Blueprint.

Serves rendered HTML templates for the end-user pages.

Routes
------
GET /          → index.html
GET /service   → service.html
GET /gap       → gap.html
"""
from __future__ import annotations

from flask import Blueprint, render_template, current_app

ui_bp = Blueprint("ui", __name__)


@ui_bp.route("/")
def index():
    return render_template("index.html")


@ui_bp.route("/service")
def service_page():
    return render_template(
        "service.html",
        enable_admin_sync=current_app.config.get("ENABLE_ADMIN_SYNC", True),
    )


@ui_bp.route("/gap")
def gap_page():
    return render_template("gap.html")

