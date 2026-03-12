from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app import app
from pricewatch.services.mapping_service import MappingService


def _make_mapping(item_id: int) -> SimpleNamespace:
    ref_store = SimpleNamespace(id=1, name="Ref Store")
    tgt_store = SimpleNamespace(id=2, name="Target Store")
    ref_cat = SimpleNamespace(
        id=10,
        name="Ref Category",
        store=ref_store,
        store_id=ref_store.id,
    )
    tgt_cat = SimpleNamespace(
        id=20,
        name="Target Category",
        store=tgt_store,
        store_id=tgt_store.id,
    )
    return SimpleNamespace(
        id=item_id,
        reference_category_id=ref_cat.id,
        target_category_id=tgt_cat.id,
        reference_category=ref_cat,
        target_category=tgt_cat,
        match_type="manual",
        confidence=0.75,
        updated_at=datetime.now(timezone.utc),
    )


def test_get_mappings_returns_names(monkeypatch):
    mapping = _make_mapping(1)

    def fake_list(self, reference_store_id=None, target_store_id=None):
        assert reference_store_id == 5
        assert target_store_id == 7
        return [mapping]

    monkeypatch.setattr(MappingService, "list_category_mappings", fake_list)

    resp = app.test_client().get("/api/category-mappings?reference_store_id=5&target_store_id=7")
    assert resp.status_code == 200
    payload = resp.get_json()
    entry = payload['mappings'][0]
    assert entry['reference_category_name'] == 'Ref Category'
    assert entry['target_store_name'] == 'Target Store'


def test_create_mapping_returns_filtered_list(monkeypatch):
    created = _make_mapping(2)
    calls: dict[str, int | float | None] = {}

    def fake_create(self, reference_category_id, target_category_id, match_type, confidence):
        calls.update({
            'reference_category_id': reference_category_id,
            'target_category_id': target_category_id,
            'match_type': match_type,
            'confidence': confidence,
        })
        return created

    def fake_list(self, reference_store_id=None, target_store_id=None):
        assert reference_store_id == 11
        assert target_store_id == 22
        return [created]

    monkeypatch.setattr(MappingService, 'create_category_mapping', fake_create)
    monkeypatch.setattr(MappingService, 'list_category_mappings', fake_list)

    client = app.test_client()
    resp = client.post(
        '/api/category-mappings?reference_store_id=11&target_store_id=22',
        json={
            'reference_category_id': 10,
            'target_category_id': 20,
            'match_type': 'auto',
            'confidence': 0.5,
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['mapping']['id'] == created.id
    assert data['mappings'][0]['reference_category_name'] == 'Ref Category'
    assert calls['match_type'] == 'auto'
    assert calls['confidence'] == 0.5


def test_update_mapping_returns_refreshed_list(monkeypatch):
    updated = _make_mapping(3)
    called = {'updated': False}

    def fake_update(self, mapping_id, match_type=None, confidence=None):
        assert mapping_id == 3
        assert match_type == 'exact'
        called['updated'] = True
        return updated

    def fake_list(self, reference_store_id=None, target_store_id=None):
        assert reference_store_id is None
        assert target_store_id is None
        return [updated]

    monkeypatch.setattr(MappingService, 'update_category_mapping', fake_update)
    monkeypatch.setattr(MappingService, 'list_category_mappings', fake_list)

    client = app.test_client()
    resp = client.put('/api/category-mappings/3', json={'match_type': 'exact'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['mapping']['id'] == updated.id
    assert called['updated']


def test_delete_mapping_returns_refreshed_list(monkeypatch):
    deleted_list = []
    calls = {'deleted': False}

    def fake_delete(self, mapping_id):
        assert mapping_id == 4
        calls['deleted'] = True

    def fake_list(self, reference_store_id=None, target_store_id=None):
        assert reference_store_id is None
        assert target_store_id is None
        return deleted_list

    monkeypatch.setattr(MappingService, 'delete_category_mapping', fake_delete)
    monkeypatch.setattr(MappingService, 'list_category_mappings', fake_list)

    resp = app.test_client().delete('/api/category-mappings/4')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['deleted'] is True
    assert calls['deleted']
    assert payload['mappings'] == []


def test_update_mapping_ignores_category_ids(monkeypatch):
    """PUT /api/category-mappings/<id> only accepts match_type/confidence.
    The category pair is immutable — reference_category_id and target_category_id
    are now rejected at the DTO boundary (extra=forbid on UpdateCategoryMappingRequest).
    This test verifies that the route correctly passes only match_type and confidence
    to the service layer when a valid payload is provided."""
    updated = _make_mapping(5)
    received = {}

    def fake_update(self, mapping_id, match_type=None, confidence=None):
        received['mapping_id'] = mapping_id
        received['match_type'] = match_type
        received['confidence'] = confidence
        return updated

    def fake_list(self, **kw):
        return [updated]

    monkeypatch.setattr(MappingService, 'update_category_mapping', fake_update)
    monkeypatch.setattr(MappingService, 'list_category_mappings', fake_list)

    resp = app.test_client().put(
        '/api/category-mappings/5',
        # Only match_type/confidence — category IDs are NOT accepted (immutable pair)
        json={'match_type': 'manual', 'confidence': 0.9},
    )
    assert resp.status_code == 200
    assert received['match_type'] == 'manual'
    assert received['confidence'] == 0.9
    assert 'reference_category_id' not in received
    assert 'target_category_id' not in received


# ---------------------------------------------------------------------------
# GET /api/categories/<id>/mapped-target-categories
# ---------------------------------------------------------------------------

def test_mapped_target_categories_returns_list(monkeypatch):
    """GET /api/categories/<id>/mapped-target-categories returns mapped targets."""
    from types import SimpleNamespace
    from app import app as flask_app
    import pricewatch.web.catalog_routes as catalog_routes_module

    ref_store = SimpleNamespace(id=1, name="Ref Store", is_reference=True, base_url=None)
    tgt_store = SimpleNamespace(id=2, name="Target Store", is_reference=False, base_url=None)
    tgt_cat = SimpleNamespace(
        id=20,
        name="Skates",
        normalized_name="skates",
        url="https://tgt.example.com/skates",
        store_id=tgt_store.id,
        store=tgt_store,
    )
    mapping = SimpleNamespace(
        id=1,
        reference_category_id=10,
        target_category_id=tgt_cat.id,
        target_category=tgt_cat,
        match_type="exact",
        confidence=1.0,
    )

    monkeypatch.setattr(
        catalog_routes_module,
        "list_mapped_target_categories",
        lambda session, ref_id, **kw: [mapping],
    )

    resp = flask_app.test_client().get("/api/categories/10/mapped-target-categories")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["mapped_target_categories"]) == 1
    entry = data["mapped_target_categories"][0]
    assert entry["target_category_id"] == 20
    assert entry["target_category_name"] == "Skates"
    assert entry["match_type"] == "exact"
    assert entry["confidence"] == 1.0
    assert entry["target_store_name"] == "Target Store"


def test_mapped_target_categories_empty(monkeypatch):
    """GET /api/categories/<id>/mapped-target-categories returns empty list when no mappings."""
    from app import app as flask_app
    import pricewatch.web.catalog_routes as catalog_routes_module

    monkeypatch.setattr(
        catalog_routes_module,
        "list_mapped_target_categories",
        lambda session, ref_id, **kw: [],
    )

    resp = flask_app.test_client().get("/api/categories/99/mapped-target-categories")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mapped_target_categories"] == []


# ---------------------------------------------------------------------------
# POST /api/category-mappings/auto-link
# ---------------------------------------------------------------------------

def test_auto_link_returns_created_and_skipped(monkeypatch):
    """POST /api/category-mappings/auto-link returns rich response with summary."""
    from app import app as flask_app
    from pricewatch.services.category_matching_service import CategoryMatchingService

    fake_result = {
        "created": [
            {"reference_category_id": 1, "reference_category_name": "Skates",
             "target_category_id": 5, "target_category_name": "Skates",
             "match_type": "exact", "confidence": 1.0},
        ],
        "skipped_existing": [],
        "summary": {"created": 1, "skipped_existing": 0, "skipped_no_norm": 0},
    }
    monkeypatch.setattr(
        CategoryMatchingService,
        "auto_link",
        staticmethod(lambda session, *, reference_store_id, target_store_id: fake_result),
    )

    resp = flask_app.test_client().post(
        "/api/category-mappings/auto-link",
        json={"reference_store_id": 1, "target_store_id": 2},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "created" in data
    assert "skipped_existing" in data
    assert "summary" in data
    assert data["summary"]["created"] == 1
    assert data["summary"]["skipped_existing"] == 0
    assert isinstance(data["created"], list)
    assert data["created"][0]["match_type"] == "exact"


def test_auto_link_returns_400_when_ids_missing():
    """POST /api/category-mappings/auto-link returns 4xx if store ids are missing.

    After Pydantic DTO migration missing required fields return 422 (Unprocessable Entity)
    rather than the old manual-validation 400.  Both 400 and 422 indicate a client error.
    """
    from app import app as flask_app

    resp = flask_app.test_client().post(
        "/api/category-mappings/auto-link",
        json={},
    )
    assert resp.status_code in (400, 422)
    assert "error" in resp.get_json()


def test_auto_link_returns_400_on_value_error(monkeypatch):
    """POST /api/category-mappings/auto-link returns 400 on ValueError from service."""
    from app import app as flask_app
    from pricewatch.services.category_matching_service import CategoryMatchingService

    def raise_error(session, *, reference_store_id, target_store_id):
        raise ValueError("Store 999 not found")

    monkeypatch.setattr(CategoryMatchingService, "auto_link", staticmethod(raise_error))

    resp = flask_app.test_client().post(
        "/api/category-mappings/auto-link",
        json={"reference_store_id": 999, "target_store_id": 2},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_auto_link_requires_json():
    """POST /api/category-mappings/auto-link returns 400 for non-JSON requests."""
    from app import app as flask_app

    resp = flask_app.test_client().post(
        "/api/category-mappings/auto-link",
        data="not-json",
        content_type="text/plain",
    )
    assert resp.status_code == 400



