"""pricewatch.web.admin_routes -- Admin Blueprint aggregator.

This module owns ``admin_bp`` and delegates all route definitions to
domain-aligned route-group modules.  It contains no route business logic.

Route groups
------------
- admin_store_sync_routes     -- store sync, category/product sync
- admin_mapping_routes        -- category mappings CRUD + auto-link
- admin_scrape_history_routes -- scrape-runs list/detail, scrape-status
- admin_scheduler_job_routes  -- scrape job control-plane
- admin_scheduler_schedule_routes -- schedule read/write
- admin_comparison_gap_routes -- comparison, confirm-match, gap, gap-status
"""
from __future__ import annotations

from flask import Blueprint

from pricewatch.web.admin_store_sync_routes import register_admin_store_sync_routes
from pricewatch.web.admin_mapping_routes import register_admin_mapping_routes
from pricewatch.web.admin_scrape_history_routes import register_admin_scrape_history_routes
from pricewatch.web.admin_scheduler_job_routes import register_admin_scheduler_job_routes
from pricewatch.web.admin_scheduler_schedule_routes import register_admin_scheduler_schedule_routes
from pricewatch.web.admin_comparison_gap_routes import register_admin_comparison_gap_routes

admin_bp = Blueprint("admin", __name__)

register_admin_store_sync_routes(admin_bp)
register_admin_mapping_routes(admin_bp)
register_admin_scrape_history_routes(admin_bp)
register_admin_scheduler_job_routes(admin_bp)
register_admin_scheduler_schedule_routes(admin_bp)
register_admin_comparison_gap_routes(admin_bp)
