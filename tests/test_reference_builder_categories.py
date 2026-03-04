from pricewatch.core.reference_service import ReferenceCatalogBuilder


class DummyAdapter:
    def __init__(self):
        self.called_with = None

    def get_categories(self, client):
        return [{'name': 'Ice', 'url': 'https://prohockey.com.ua/catalog/ice'}]

    def scrape_category(self, client, category=None):
        # record what was passed and return empty list
        self.called_with = category
        return []


class DummyClient:
    def __init__(self):
        self.session = None


def test_reference_builder_accepts_category_dicts():
    adapter = DummyAdapter()
    client = DummyClient()
    builder = ReferenceCatalogBuilder(adapter, client)
    res = builder.build()
    # Should return empty results (adapter.scrape_category returned [])
    assert res == []
    # Adapter should have been called with normalized category string 'Ice'
    assert adapter.called_with == 'Ice'

