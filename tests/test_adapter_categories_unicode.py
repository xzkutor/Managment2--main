from app import app
from pricewatch.core.registry import get_registry

class EscapedAdapter:
    def __init__(self):
        self.name = 'escaped'
        self.domains = ()
    def get_categories(self, client):
        # '\u041f\u0440\u0438\u0432\u0456\u0442' -> 'Привіт' (Ukrainian hello)
        return [{'name': '\\u041f\\u0440\\u0438\\u0432\\u0456\\u0442', 'url': 'https://example/'}]


def test_adapter_categories_unicode_decoded(monkeypatch):
    registry = get_registry()
    orig = registry.adapters
    registry.adapters = [EscapedAdapter()]
    try:
        client = app.test_client()
        resp = client.get('/api/adapters/escaped/categories')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'categories' in data
        cats = data['categories']
        assert isinstance(cats, list) and len(cats) == 1
        name = cats[0]['name']
        # Expect decoded UTF-8 string (contains Cyrillic characters)
        assert 'Пр' in name or 'П' in name
    finally:
        registry.adapters = orig

