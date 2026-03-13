"""Regression tests for the stable API contract.

Covers:
  - GET /api/stores          — DB read-only, no sync side-effects
  - POST /api/admin/stores/sync — admin-only, disabled when ENABLE_ADMIN_SYNC=False
  - GET /api/category-mappings
  - POST /api/category-mappings
  - PUT /api/category-mappings/<id>  — category pair is immutable
  - DELETE /api/category-mappings/<id>
  - GET /api/scrape-runs
  - GET /api/scrape-runs/<id>
  - GET /api/scrape-status
  - GET /api/adapters/<name>/categories — 200 known, 404 unknown
  - POST /api/scrape  — must not exist (removed)
"""
from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

app_module = importlib.import_module("app")
from app import app  # noqa: E402 — after sys.path is set by PYTHONPATH=.
import pricewatch.web.catalog_routes as catalog_routes_module
from pricewatch.services.mapping_service import MappingService
from pricewatch.services.scrape_history_service import ScrapeHistoryService
from pricewatch.services.store_service import StoreService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store(store_id: int = 1, name: str = "Store", is_reference: bool = False) -> SimpleNamespace:
    return SimpleNamespace(id=store_id, name=name, is_reference=is_reference, base_url="https://example.com")


def _make_mapping(item_id: int = 1) -> SimpleNamespace:
    ref_store = SimpleNamespace(id=1, name="Ref Store")
    tgt_store = SimpleNamespace(id=2, name="Target Store")
    ref_cat = SimpleNamespace(id=10, name="Ref Cat", store=ref_store, store_id=1)
    tgt_cat = SimpleNamespace(id=20, name="Tgt Cat", store=tgt_store, store_id=2)
    return SimpleNamespace(
        id=item_id,
        reference_category_id=10,
        target_category_id=20,
        reference_category=ref_cat,
        target_category=tgt_cat,
        match_type="manual",
        confidence=0.8,
        updated_at=datetime.now(timezone.utc),
    )


def _make_run(run_id: int = 1, status: str = "finished") -> SimpleNamespace:
    store = _store(1, "TestStore")
    return SimpleNamespace(
        id=run_id,
        store_id=store.id,
        store=store,
        run_type="categories",
        status=status,
        started_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        finished_at=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
        categories_processed=3,
        products_processed=50,
        products_created=40,
        products_updated=10,
        price_changes_detected=2,
        error_message=None,
        metadata_json=None,
    )


# ---------------------------------------------------------------------------
# GET /api/stores  — must be read-only
# ---------------------------------------------------------------------------

class TestGetStores:
    def test_returns_200_with_stores_key(self, monkeypatch):
        monkeypatch.setattr(catalog_routes_module, "list_stores", lambda session: [_store(1, "S1")])
        resp = app.test_client().get("/api/stores")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stores" in data
        assert len(data["stores"]) == 1
        assert data["stores"][0]["name"] == "S1"

    def test_does_not_call_sync_with_registry(self, monkeypatch):
        """GET /api/stores must never trigger sync_with_registry."""
        monkeypatch.setattr(
            StoreService,
            "sync_with_registry",
            lambda self, reg: (_ for _ in ()).throw(AssertionError("sync must not run on GET /api/stores")),
        )
        monkeypatch.setattr(catalog_routes_module, "list_stores", lambda session: [])
        resp = app.test_client().get("/api/stores")
        assert resp.status_code == 200

    def test_response_shape(self, monkeypatch):
        monkeypatch.setattr(
            catalog_routes_module,
            "list_stores",
            lambda session: [_store(7, "MyStore", is_reference=True)],
        )
        resp = app.test_client().get("/api/stores")
        store = resp.get_json()["stores"][0]
        for key in ("id", "name", "is_reference", "base_url"):
            assert key in store, f"missing key: {key}"
        assert store["is_reference"] is True

    def test_post_not_allowed(self):
        """Stores endpoint must be strictly read-only — POST must return 405."""
        resp = app.test_client().post("/api/stores", json={})
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# POST /api/admin/stores/sync
# ---------------------------------------------------------------------------

class TestAdminStoreSync:
    def test_returns_synced_stores(self, monkeypatch):
        stores = [_store(3, "Synced")]
        monkeypatch.setattr(StoreService, "sync_with_registry", lambda self, reg: stores)
        resp = app.test_client().post("/api/admin/stores/sync")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["stores"][0]["name"] == "Synced"

    def test_disabled_returns_404(self, monkeypatch):
        monkeypatch.setitem(app.config, "ENABLE_ADMIN_SYNC", False)
        resp = app.test_client().post("/api/admin/stores/sync")
        assert resp.status_code == 404
        # Restore
        monkeypatch.setitem(app.config, "ENABLE_ADMIN_SYNC", True)

    def test_get_not_allowed(self):
        resp = app.test_client().get("/api/admin/stores/sync")
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# GET /api/category-mappings
# ---------------------------------------------------------------------------

class TestListCategoryMappings:
    def test_returns_mappings_key(self, monkeypatch):
        m = _make_mapping(1)
        monkeypatch.setattr(MappingService, "list_category_mappings", lambda self, **kw: [m])
        resp = app.test_client().get("/api/category-mappings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "mappings" in data
        assert len(data["mappings"]) == 1

    def test_passes_filter_params(self, monkeypatch):
        received = {}

        def fake_list(self, reference_store_id=None, target_store_id=None):
            received.update(ref=reference_store_id, tgt=target_store_id)
            return []

        monkeypatch.setattr(MappingService, "list_category_mappings", fake_list)
        app.test_client().get("/api/category-mappings?reference_store_id=3&target_store_id=5")
        assert received["ref"] == 3
        assert received["tgt"] == 5

    def test_mapping_shape(self, monkeypatch):
        m = _make_mapping(42)
        monkeypatch.setattr(MappingService, "list_category_mappings", lambda self, **kw: [m])
        entry = app.test_client().get("/api/category-mappings").get_json()["mappings"][0]
        for key in (
            "id", "reference_category_id", "target_category_id",
            "reference_category_name", "target_category_name",
            "reference_store_name", "target_store_name",
            "match_type", "confidence",
        ):
            assert key in entry, f"missing key: {key}"
        assert entry["id"] == 42


# ---------------------------------------------------------------------------
# POST /api/category-mappings
# ---------------------------------------------------------------------------

class TestCreateCategoryMapping:
    def test_returns_mapping_and_list(self, monkeypatch):
        created = _make_mapping(99)
        monkeypatch.setattr(MappingService, "create_category_mapping", lambda self, **kw: created)
        monkeypatch.setattr(MappingService, "list_category_mappings", lambda self, **kw: [created])

        resp = app.test_client().post(
            "/api/category-mappings",
            json={"reference_category_id": 10, "target_category_id": 20, "match_type": "auto", "confidence": 0.6},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mapping"]["id"] == 99
        assert "mappings" in data

    def test_400_on_service_error(self, monkeypatch):
        def fail(self, **kw):
            raise ValueError("duplicate mapping")

        monkeypatch.setattr(MappingService, "create_category_mapping", fail)
        # Send a valid payload so Pydantic passes; error comes from the service layer (400)
        resp = app.test_client().post(
            "/api/category-mappings",
            json={"reference_category_id": 10, "target_category_id": 20},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# PUT /api/category-mappings/<id>  — immutable category pair
# ---------------------------------------------------------------------------

class TestUpdateCategoryMapping:
    def test_only_forwards_match_type_and_confidence(self, monkeypatch):
        updated = _make_mapping(5)
        received: dict = {}

        def fake_update(self, mapping_id, match_type=None, confidence=None):
            received["mapping_id"] = mapping_id
            received["match_type"] = match_type
            received["confidence"] = confidence
            return updated

        monkeypatch.setattr(MappingService, "update_category_mapping", fake_update)
        monkeypatch.setattr(MappingService, "list_category_mappings", lambda self, **kw: [updated])

        app.test_client().put(
            "/api/category-mappings/5",
            json={
                # reference_category_id and target_category_id are NOT sent —
                # the PUT schema only accepts match_type/confidence (pair is immutable)
                "match_type": "exact",
                "confidence": 0.99,
            },
        )
        assert received["match_type"] == "exact"
        assert received["confidence"] == 0.99
        assert "reference_category_id" not in received
        assert "target_category_id" not in received

    def test_returns_updated_mapping(self, monkeypatch):
        updated = _make_mapping(6)
        monkeypatch.setattr(MappingService, "update_category_mapping", lambda self, mid, **kw: updated)
        monkeypatch.setattr(MappingService, "list_category_mappings", lambda self, **kw: [updated])
        data = app.test_client().put("/api/category-mappings/6", json={"match_type": "manual"}).get_json()
        assert data["mapping"]["id"] == 6

    def test_400_on_service_error(self, monkeypatch):
        def fail(self, mapping_id, **kw):
            raise ValueError("not found")

        monkeypatch.setattr(MappingService, "update_category_mapping", fail)
        resp = app.test_client().put("/api/category-mappings/9999", json={})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/category-mappings/<id>
# ---------------------------------------------------------------------------

class TestDeleteCategoryMapping:
    def test_returns_deleted_true(self, monkeypatch):
        monkeypatch.setattr(MappingService, "delete_category_mapping", lambda self, mid: None)
        monkeypatch.setattr(MappingService, "list_category_mappings", lambda self, **kw: [])
        data = app.test_client().delete("/api/category-mappings/4").get_json()
        assert data["deleted"] is True
        assert data["mapping_id"] == 4
        assert data["mappings"] == []

    def test_400_on_service_error(self, monkeypatch):
        def fail(self, mapping_id):
            raise ValueError("not found")

        monkeypatch.setattr(MappingService, "delete_category_mapping", fail)
        resp = app.test_client().delete("/api/category-mappings/9999")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/scrape-runs
# ---------------------------------------------------------------------------

class TestListScrapeRuns:
    def test_returns_runs_key(self, monkeypatch):
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [_make_run(1)])
        resp = app.test_client().get("/api/scrape-runs")
        assert resp.status_code == 200
        assert "runs" in resp.get_json()

    def test_response_shape(self, monkeypatch):
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [_make_run(2)])
        run = app.test_client().get("/api/scrape-runs").get_json()["runs"][0]
        for key in ("id", "store_id", "store", "run_type", "status", "started_at", "finished_at",
                    "categories_processed", "products_processed", "products_created",
                    "products_updated", "price_changes_detected", "error_message"):
            assert key in run, f"missing key: {key}"

    def test_passes_query_filters(self, monkeypatch):
        received: dict = {}

        def fake_list(self, *, store_id=None, run_type=None, status=None,
                      trigger_type=None, limit=None, offset=None):
            received.update(store_id=store_id, run_type=run_type, status=status,
                            trigger_type=trigger_type, limit=limit, offset=offset)
            return []

        monkeypatch.setattr(ScrapeHistoryService, "list_runs", fake_list)
        app.test_client().get(
            "/api/scrape-runs?store_id=2&run_type=categories&status=finished&limit=5&offset=10"
        )
        assert received["store_id"] == 2
        assert received["run_type"] == "categories"
        assert received["status"] == "finished"
        assert received["limit"] == 5
        assert received["offset"] == 10


# ---------------------------------------------------------------------------
# GET /api/scrape-runs/<id>
# ---------------------------------------------------------------------------

class TestGetScrapeRun:
    def test_returns_run_key(self, monkeypatch):
        run = _make_run(7)
        monkeypatch.setattr(ScrapeHistoryService, "get_run", lambda self, run_id: run)
        data = app.test_client().get("/api/scrape-runs/7").get_json()
        assert "run" in data
        assert data["run"]["id"] == 7

    def test_404_for_missing(self, monkeypatch):
        def fail(self, run_id):
            raise ValueError(f"ScrapeRun {run_id} not found")

        monkeypatch.setattr(ScrapeHistoryService, "get_run", fail)
        resp = app.test_client().get("/api/scrape-runs/9999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# GET /api/scrape-status
# ---------------------------------------------------------------------------

class TestScrapeStatus:
    def test_returns_runs_key(self, monkeypatch):
        monkeypatch.setattr(ScrapeHistoryService, "list_runs", lambda self, **kw: [_make_run(1)])
        resp = app.test_client().get("/api/scrape-status")
        assert resp.status_code == 200
        assert "runs" in resp.get_json()

    def test_defaults_to_running_status(self, monkeypatch):
        received: dict = {}

        def fake_list(self, *, store_id=None, run_type=None, status=None, limit=None, offset=None):
            received["status"] = status
            return []

        monkeypatch.setattr(ScrapeHistoryService, "list_runs", fake_list)
        app.test_client().get("/api/scrape-status")
        assert received["status"] == "running"

    def test_accepts_store_id_filter(self, monkeypatch):
        received: dict = {}

        def fake_list(self, *, store_id=None, run_type=None, status=None, limit=None, offset=None):
            received["store_id"] = store_id
            return []

        monkeypatch.setattr(ScrapeHistoryService, "list_runs", fake_list)
        app.test_client().get("/api/scrape-status?store_id=4")
        assert received["store_id"] == 4


# ---------------------------------------------------------------------------
# GET /api/adapters / GET /api/adapters/<adapter_name>/categories
# (internal/admin-facing adapter runtime introspection — NOT canonical DB-first API)
# ---------------------------------------------------------------------------

class _DummyAdapter:
    name = "testadapter"
    domains = ()
    is_reference = False

    def get_categories(self, client):
        return [{"name": "Alpha", "url": "https://a/"}, {"name": "Beta", "url": "https://b/"}]


class TestAdapterCategories:
    """Regression contract for adapter runtime introspection endpoints.

    These endpoints (GET /api/adapters, GET /api/adapters/<name>/categories) are
    **supported internal/admin-facing** endpoints, NOT part of the canonical DB-first API.
    Normal UI flows use GET /api/stores/<store_id>/categories instead.

    Tests here verify that the endpoints remain operational and return the expected shape.
    """

    def test_known_adapter_returns_200(self, monkeypatch):
        """Known adapter name returns 200 with a 'categories' list."""
        from pricewatch.core.registry import get_registry
        registry = get_registry()
        orig = registry.adapters
        registry.adapters = [_DummyAdapter()]
        try:
            resp = app.test_client().get("/api/adapters/testadapter/categories")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "categories" in data
            assert any(c["name"] == "Alpha" for c in data["categories"])
        finally:
            registry.adapters = orig

    def test_unknown_adapter_returns_404(self, monkeypatch):
        """Unknown adapter name returns 404 with an 'error' key."""
        from pricewatch.core.registry import get_registry
        registry = get_registry()
        orig = registry.adapters
        registry.adapters = []
        try:
            resp = app.test_client().get("/api/adapters/nonexistent/categories")
            assert resp.status_code == 404
            assert "error" in resp.get_json()
        finally:
            registry.adapters = orig

    def test_route_requires_adapter_name_segment(self):
        """URL without adapter_name segment must not match this route (405 or 404)."""
        resp = app.test_client().get("/api/adapters//categories")
        # Flask resolves double-slash as a redirect or 404; either way not 200
        assert resp.status_code != 200


# ---------------------------------------------------------------------------
# POST /api/scrape — must NOT exist (endpoint was removed)
# ---------------------------------------------------------------------------

class TestRemovedScrapeEndpoint:
    def test_scrape_endpoint_removed(self):
        """POST /api/scrape was removed; must return 404 or 405, never 200/501."""
        resp = app.test_client().post("/api/scrape", json={})
        assert resp.status_code in (404, 405), (
            f"Expected 404/405 after removal of /api/scrape, got {resp.status_code}"
        )

