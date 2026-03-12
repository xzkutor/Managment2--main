"""Tests for GET /api/adapters/<adapter_name>/categories (internal/admin-facing endpoint).

This endpoint is a supported internal/admin-facing adapter runtime introspection endpoint.
It is NOT part of the canonical DB-first catalog API.
Normal UI flows use GET /api/stores/<store_id>/categories instead.

Coverage here verifies that the endpoint remains operational and returns the expected shape,
which is needed for adapter introspection and operational workflows.
"""

import json  # noqa: F401 — kept for backwards compatibility if any consumer imports this module
from app import app
from pricewatch.core.registry import get_registry


class DummyAdapter:
    def __init__(self, name):
        self.name = name
        self.domains = ()

    def get_categories(self, client):
        return [{'name': 'One', 'url': 'https://one/'}, {'name': 'Two', 'url': 'https://two/'}]


def test_adapter_categories_endpoint(monkeypatch):
    """GET /api/adapters/<name>/categories returns live categories from the named adapter."""
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

