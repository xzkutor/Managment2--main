"""Tests for store-scoped categories endpoints.

Primary coverage:  GET /api/stores/<store_id>/categories  (canonical)
Compat coverage:   GET /api/categories                    (compatibility — migration target)

The canonical endpoint is the preferred path for all new consumer code.
GET /api/categories is kept operational for backwards compatibility only; its
compat coverage here validates that it still returns the expected shape but
does not add new assertions beyond what is needed to detect regressions.
"""
from __future__ import annotations

from types import SimpleNamespace

import pricewatch.web.catalog_routes as catalog_routes_module
from app import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_category(cat_id: int = 10, store_id: int = 1, name: str = "Ковзани"):
    return SimpleNamespace(
        id=cat_id,
        store_id=store_id,
        name=name,
        normalized_name=name.lower(),
        url="https://example.com/skates",
        external_id="cat-1",
        updated_at=None,
    )


# ---------------------------------------------------------------------------
# GET /api/stores/<store_id>/categories  — canonical endpoint
# ---------------------------------------------------------------------------

class TestStoreCategories:
    """Tests for the canonical GET /api/stores/<store_id>/categories endpoint."""

    def test_returns_200_with_categories_key(self, monkeypatch):
        cats = [_make_category(10, 1, "Ковзани")]
        monkeypatch.setattr(catalog_routes_module, "list_categories_by_store", lambda session, sid: cats)
        monkeypatch.setattr(catalog_routes_module, "count_products_by_category", lambda session, sid: {10: 5})

        resp = app.test_client().get("/api/stores/1/categories")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_category_shape(self, monkeypatch):
        cats = [_make_category(10, 1, "Ковзани")]
        monkeypatch.setattr(catalog_routes_module, "list_categories_by_store", lambda session, sid: cats)
        monkeypatch.setattr(catalog_routes_module, "count_products_by_category", lambda session, sid: {10: 42})

        resp = app.test_client().get("/api/stores/1/categories")
        cat = resp.get_json()["categories"][0]

        for key in ("id", "store_id", "name", "url", "product_count"):
            assert key in cat, f"missing key: {key}"
        assert cat["product_count"] == 42

    def test_empty_store_returns_empty_list(self, monkeypatch):
        monkeypatch.setattr(catalog_routes_module, "list_categories_by_store", lambda session, sid: [])
        monkeypatch.setattr(catalog_routes_module, "count_products_by_category", lambda session, sid: {})

        resp = app.test_client().get("/api/stores/99/categories")

        assert resp.status_code == 200
        assert resp.get_json()["categories"] == []

    def test_product_count_zero_when_no_products(self, monkeypatch):
        cats = [_make_category(10, 1, "Ковзани")]
        monkeypatch.setattr(catalog_routes_module, "list_categories_by_store", lambda session, sid: cats)
        monkeypatch.setattr(catalog_routes_module, "count_products_by_category", lambda session, sid: {})

        resp = app.test_client().get("/api/stores/1/categories")
        cat = resp.get_json()["categories"][0]

        assert cat["product_count"] == 0

    def test_post_not_allowed(self):
        resp = app.test_client().post("/api/stores/1/categories", json={})
        assert resp.status_code == 405

    def test_does_not_include_store_key_in_response(self, monkeypatch):
        """Canonical endpoint returns only 'categories' — no implicit store metadata."""
        monkeypatch.setattr(catalog_routes_module, "list_categories_by_store", lambda session, sid: [])
        monkeypatch.setattr(catalog_routes_module, "count_products_by_category", lambda session, sid: {})

        data = app.test_client().get("/api/stores/1/categories").get_json()

        assert "store" not in data, (
            "Canonical endpoint must not include 'store' key; "
            "caller already knows the store_id from the path parameter."
        )


# ---------------------------------------------------------------------------
# GET /api/categories  — compatibility endpoint (migration target)
# ---------------------------------------------------------------------------

class TestCategoriesCompatEndpoint:
    """Minimal regression coverage for the compat GET /api/categories endpoint.

    Do NOT expand this test class with new assertions or new consumer code.
    This class exists only to detect regressions in the compatibility endpoint
    while the migration to the canonical endpoint is in progress.
    """

    def test_returns_200_with_categories_key(self):
        """Compat endpoint must remain operational and return the expected shape."""
        resp = app.test_client().get("/api/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
