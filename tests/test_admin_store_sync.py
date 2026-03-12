from types import SimpleNamespace
import importlib

app_module = importlib.import_module("app")
import pricewatch.web.catalog_routes as catalog_routes_module
from pricewatch.services.store_service import StoreService


def test_api_stores_get_is_read_only(monkeypatch):
    monkeypatch.setattr(
        StoreService,
        "sync_with_registry",
        lambda self, registry: (_ for _ in ()).throw(AssertionError("sync_with_registry should not run on GET /api/stores")),
    )
    monkeypatch.setattr(
        catalog_routes_module,
        "list_stores",
        lambda session: [SimpleNamespace(id=1, name="dummy", is_reference=False, base_url="https://dummy")],
    )

    client = app_module.app.test_client()
    resp = client.get('/api/stores')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['stores'][0]['name'] == 'dummy'


def test_admin_store_sync_endpoint(monkeypatch):
    stores = [SimpleNamespace(id=2, name="synced", is_reference=False, base_url="https://synced")]

    def fake_sync(self, registry):
        return stores

    monkeypatch.setattr(StoreService, "sync_with_registry", fake_sync)

    client = app_module.app.test_client()
    resp = client.post('/api/admin/stores/sync')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['stores'][0]['name'] == 'synced'

    monkeypatch.setitem(app_module.app.config, 'ENABLE_ADMIN_SYNC', False)
    resp_disabled = client.post('/api/admin/stores/sync')
    assert resp_disabled.status_code == 404

