import json
from app import app
from pricewatch.core.registry import get_registry


class DummyAdapter:
    def __init__(self, name):
        self.name = name
        self.domains = ()

    def get_categories(self, client):
        return [{'name': 'One', 'url': 'https://one/'}, {'name': 'Two', 'url': 'https://two/'}]


def test_adapter_categories_endpoint(monkeypatch):
    # replace registry adapters with our dummy
    registry = get_registry()
    orig = registry.adapters
    registry.adapters = [DummyAdapter('dummy')]
    try:
        client = app.test_client()
        resp = client.get('/api/adapters/dummy/categories')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'categories' in data
        assert isinstance(data['categories'], list)
        assert any(c['name'] == 'One' for c in data['categories'])
    finally:
        registry.adapters = orig

