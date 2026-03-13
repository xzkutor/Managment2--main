"""tests/test_admin_routes_split.py -- Smoke tests for the admin route split.

Verifies that after splitting admin_routes.py into domain-aligned modules:
- admin_bp is still the single shared blueprint registration surface
- each route-group module registers its routes correctly
- representative endpoints from each group are present and reachable
- no duplicate route registrations occur
- app factory still starts cleanly with the split structure
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------

class TestModuleImports:

    def test_admin_routes_aggregator_importable(self):
        from pricewatch.web.admin_routes import admin_bp
        assert admin_bp is not None
        assert admin_bp.name == "admin"

    def test_store_sync_module_importable(self):
        from pricewatch.web.admin_store_sync_routes import register_admin_store_sync_routes
        assert callable(register_admin_store_sync_routes)

    def test_mapping_module_importable(self):
        from pricewatch.web.admin_mapping_routes import register_admin_mapping_routes
        assert callable(register_admin_mapping_routes)

    def test_scrape_history_module_importable(self):
        from pricewatch.web.admin_scrape_history_routes import register_admin_scrape_history_routes
        assert callable(register_admin_scrape_history_routes)

    def test_scheduler_job_module_importable(self):
        from pricewatch.web.admin_scheduler_job_routes import register_admin_scheduler_job_routes
        assert callable(register_admin_scheduler_job_routes)

    def test_scheduler_schedule_module_importable(self):
        from pricewatch.web.admin_scheduler_schedule_routes import register_admin_scheduler_schedule_routes
        assert callable(register_admin_scheduler_schedule_routes)

    def test_comparison_gap_module_importable(self):
        from pricewatch.web.admin_comparison_gap_routes import register_admin_comparison_gap_routes
        assert callable(register_admin_comparison_gap_routes)


# ---------------------------------------------------------------------------
# Blueprint identity tests
# ---------------------------------------------------------------------------

class TestBlueprintIdentity:

    def test_admin_bp_name_is_admin(self):
        from pricewatch.web.admin_routes import admin_bp
        assert admin_bp.name == "admin"

    def test_admin_bp_is_single_instance(self):
        """Multiple imports must return the same blueprint object."""
        from pricewatch.web.admin_routes import admin_bp as bp1
        from pricewatch.web.admin_routes import admin_bp as bp2
        assert bp1 is bp2

    def test_app_registers_admin_bp(self, monkeypatch):
        """The Flask app factory must register admin_bp without error."""
        from pricewatch.app_factory import create_app
        app = create_app({"TESTING": True})
        # admin blueprint should be in the registered blueprints
        assert "admin" in app.blueprints


# ---------------------------------------------------------------------------
# Route presence tests (using Flask url_map)
# ---------------------------------------------------------------------------

class TestRoutePresence:
    """Check that representative routes from each group are registered."""

    @pytest.fixture(scope="class")
    def app(self):
        from pricewatch.app_factory import create_app
        return create_app({"TESTING": True})

    def _routes(self, app):
        return {rule.rule for rule in app.url_map.iter_rules()}

    # Store/sync routes
    def test_stores_sync_route_present(self, app):
        assert "/api/admin/stores/sync" in self._routes(app)

    def test_categories_sync_route_present(self, app):
        assert "/api/stores/<int:store_id>/categories/sync" in self._routes(app)

    def test_products_sync_route_present(self, app):
        assert "/api/categories/<int:category_id>/products/sync" in self._routes(app)

    # Mapping routes
    def test_category_mappings_list_route_present(self, app):
        assert "/api/category-mappings" in self._routes(app)

    def test_category_mappings_autolink_route_present(self, app):
        assert "/api/category-mappings/auto-link" in self._routes(app)

    def test_category_mapping_detail_route_present(self, app):
        assert "/api/category-mappings/<int:mapping_id>" in self._routes(app)

    # Scrape history routes
    def test_scrape_runs_list_route_present(self, app):
        assert "/api/scrape-runs" in self._routes(app)

    def test_scrape_run_detail_route_present(self, app):
        assert "/api/scrape-runs/<int:run_id>" in self._routes(app)

    def test_scrape_status_route_present(self, app):
        assert "/api/scrape-status" in self._routes(app)

    # Scheduler job routes
    def test_scrape_jobs_list_route_present(self, app):
        assert "/api/admin/scrape/jobs" in self._routes(app)

    def test_scrape_job_detail_route_present(self, app):
        assert "/api/admin/scrape/jobs/<int:job_id>" in self._routes(app)

    def test_scrape_job_run_route_present(self, app):
        assert "/api/admin/scrape/jobs/<int:job_id>/run" in self._routes(app)

    def test_scrape_job_runs_list_route_present(self, app):
        assert "/api/admin/scrape/jobs/<int:job_id>/runs" in self._routes(app)

    # Scheduler schedule routes
    def test_scrape_job_schedule_route_present(self, app):
        assert "/api/admin/scrape/jobs/<int:job_id>/schedule" in self._routes(app)

    # Comparison/gap routes
    def test_comparison_route_present(self, app):
        assert "/api/comparison" in self._routes(app)

    def test_comparison_confirm_match_route_present(self, app):
        assert "/api/comparison/confirm-match" in self._routes(app)

    def test_gap_route_present(self, app):
        assert "/api/gap" in self._routes(app)

    def test_gap_status_route_present(self, app):
        assert "/api/gap/status" in self._routes(app)


# ---------------------------------------------------------------------------
# No duplicate registration test
# ---------------------------------------------------------------------------

class TestNoDuplicateRegistration:

    def test_no_duplicate_routes(self):
        """No AssertionError or duplicate-route error when registering admin_bp.

        Flask automatically adds OPTIONS (and HEAD for GET) to every route,
        so we only check that no two *explicitly registered* HTTP methods
        appear for the same path. We exclude the Flask-injected methods.
        """
        from pricewatch.app_factory import create_app
        app = create_app({"TESTING": True})
        flask_injected = {"OPTIONS", "HEAD"}
        seen: set = set()
        for rule in app.url_map.iter_rules():
            for method in (rule.methods or set()) - flask_injected:
                key = (rule.rule, method)
                assert key not in seen, f"Duplicate route registration: {key}"
                seen.add(key)

