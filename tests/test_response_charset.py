from app import app
from pricewatch.core.registry import get_registry


def test_api_response_has_charset(monkeypatch):
    # avoid touching real adapters
    registry = get_registry()
    orig = registry.adapters
    registry.adapters = []
    try:
        client = app.test_client()
        resp = client.get('/api/adapters')
        assert resp.status_code == 200
        ct = resp.headers.get('Content-Type', '')
        assert 'charset=utf-8' in ct.lower()
    finally:
        registry.adapters = orig

