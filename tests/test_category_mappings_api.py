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
