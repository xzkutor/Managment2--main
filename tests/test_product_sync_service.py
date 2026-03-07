from types import SimpleNamespace

import pricewatch.services.product_sync_service as product_sync_service
from pricewatch.services.product_sync_service import ProductSyncService


class DummyCategory:
    def __init__(self):
        self.id = 42
        self.external_id = "ext-42"
        self.name = "GOODS"
        self.url = "https://example.com/goods"
        self.store = type("Store", (), {"id": 1, "name": "dummy"})


class DummyAdapter:
    def __init__(self):
        self.called = None

    def get_products_by_category(self, category, client=None):
        self.called = (category, client)
        return []

    def scrape_category(self, client, category):
        return []


def test_fetch_products_uses_category_dto(monkeypatch):
    dummy_client = object()
    monkeypatch.setattr(product_sync_service, "default_client", dummy_client)

    service = ProductSyncService(session=None)
    adapter = DummyAdapter()
    category = DummyCategory()

    service._fetch_products(adapter, category)

    expected = {
        "id": category.id,
        "external_id": category.external_id,
        "name": category.name,
        "url": category.url,
    }

    assert adapter.called is not None
    called_category, called_client = adapter.called
    assert called_category == expected
    assert called_client is dummy_client


def test_sync_skips_products_without_urls(monkeypatch):
    items = [
        {"name": "Missing", "product_url": None},
        {"name": "Whitespace", "url": "   "},
        {"name": "Valid", "url": "/p/123"},
    ]

    class StubAdapter:
        def get_products_by_category(self, category, client=None):
            return items

        def scrape_category(self, client, category):
            return []

    store = SimpleNamespace(id=5, name="store")
    category = SimpleNamespace(
        id=7,
        name="Cat",
        url="https://example.com/cat",
        external_id="cat-7",
        store=store,
    )

    def fake_start_run(session, *, store_id, run_type, metadata_json=None):
        return SimpleNamespace(
            id=99,
            store_id=store_id,
            run_type=run_type,
            status="running",
            metadata_json=metadata_json,
        )

    finish_called = []

    def fake_finish_run(session, run_id, **kwargs):
        finish_called.append(run_id)
        return SimpleNamespace(id=run_id, metadata_json={})

    upsert_calls = []

    def fake_upsert_product(session, *, product_url=None, **kwargs):
        upsert_calls.append(product_url)
        return (SimpleNamespace(id=1), True, False)

    monkeypatch.setattr(product_sync_service, "start_run", fake_start_run)
    monkeypatch.setattr(product_sync_service, "finish_run", fake_finish_run)
    monkeypatch.setattr(product_sync_service, "fail_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(product_sync_service, "update_counters", lambda *args, **kwargs: None)
    monkeypatch.setattr(product_sync_service, "list_products_by_category", lambda session, category_id: [])
    monkeypatch.setattr(product_sync_service, "upsert_product", fake_upsert_product)
    monkeypatch.setattr(product_sync_service, "resolve_adapter_for_store", lambda store: StubAdapter())
    monkeypatch.setattr(ProductSyncService, "_get_category", lambda self, category_id: category)

    service = ProductSyncService(session=None)
    result = service.sync_category_products(category.id)

    assert len(upsert_calls) == 1
    expected_url = "https://example.com/p/123"
    assert upsert_calls[0] == expected_url
    assert result["summary"]["skipped_invalid_products"] == 2
    assert result["summary"]["skipped_missing_url"] == 2
    counts = result["summary"]["validation_error_counts"]
    assert counts.get("missing_product_url") == 2
    sample = result["summary"]["validation_errors_sample"]
    assert len(sample) == 2
    assert sample[0]["type"] == "missing_product_url"
    assert result["scrape_run"].metadata_json["skipped_invalid_products"] == 2
    assert result["scrape_run"].metadata_json["validation_error_counts"]["missing_product_url"] == 2


def test_normalize_uses_explicit_price_numeric():
    service = ProductSyncService(session=None)
    item = {"name": "ExplicitPrice", "price": 123.45, "price_raw": "$999.00", "currency": None}
    normalized = service._normalize_product_dto(item, None)
    assert normalized["price"] == 123.45


def test_normalize_parses_price_raw_when_no_explicit(monkeypatch):
    # Подменим parse_price_value чтобы вернуть ожидаемые значения
    monkeypatch.setattr(product_sync_service, "parse_price_value", lambda raw: (99.0, "EUR"))
    service = ProductSyncService(session=None)
    item = {"name": "FromRaw", "price_raw": "€99.00"}
    normalized = service._normalize_product_dto(item, None)
    assert normalized["price"] == 99.0
    assert normalized["currency"] == "EUR"


def test_currency_explicit_overrides_parsed(monkeypatch):
    monkeypatch.setattr(product_sync_service, "parse_price_value", lambda raw: (10.0, "USD"))
    service = ProductSyncService(session=None)
    item = {"name": "CurrencyExplicit", "price_raw": "$10.00", "currency": "GBP"}
    normalized = service._normalize_product_dto(item, None)
    assert normalized["price"] == 10.0
    assert normalized["currency"] == "GBP"


def test_source_url_preferred_and_normalized():
    service = ProductSyncService(session=None)
    category_url = "https://example.com/cat/"
    # source_url is relative and should be joined with category_url
    item = {"name": "WithSource", "source_url": "/s/path", "source_site": "https://legacy.example.com"}
    normalized = service._normalize_product_dto(item, category_url)
    assert normalized["source_url"] == "https://example.com/s/path"

    # object-style DTO should также work
    obj = SimpleNamespace(name="Obj", price=5)
    normalized_obj = service._normalize_product_dto(obj, None)
    assert normalized_obj["price"] == 5
from types import SimpleNamespace

import pricewatch.services.product_sync_service as product_sync_service
from pricewatch.services.product_sync_service import ProductSyncService


class DummyCategory:
    def __init__(self):
        self.id = 42
        self.external_id = "ext-42"
        self.name = "GOODS"
        self.url = "https://example.com/goods"
        self.store = type("Store", (), {"id": 1, "name": "dummy"})


class DummyAdapter:
    def __init__(self):
        self.called = None

    def get_products_by_category(self, category, client=None):
        self.called = (category, client)
        return []

    def scrape_category(self, client, category):
        return []


def test_fetch_products_uses_category_dto(monkeypatch):
    dummy_client = object()
    monkeypatch.setattr(product_sync_service, "default_client", dummy_client)

    service = ProductSyncService(session=None)
    adapter = DummyAdapter()
    category = DummyCategory()

    service._fetch_products(adapter, category)

    expected = {
        "id": category.id,
        "external_id": category.external_id,
        "name": category.name,
        "url": category.url,
    }

    assert adapter.called is not None
    called_category, called_client = adapter.called
    assert called_category == expected
    assert called_client is dummy_client


def test_sync_skips_products_without_urls(monkeypatch):
    items = [
        {"name": "Missing", "product_url": None},
        {"name": "Whitespace", "url": "   "},
        {"name": "Valid", "url": "/p/123"},
    ]

    class StubAdapter:
        def get_products_by_category(self, category, client=None):
            return items

        def scrape_category(self, client, category):
            return []

    store = SimpleNamespace(id=5, name="store")
    category = SimpleNamespace(
        id=7,
        name="Cat",
        url="https://example.com/cat",
        external_id="cat-7",
        store=store,
    )

    def fake_start_run(session, *, store_id, run_type, metadata_json=None):
        return SimpleNamespace(
            id=99,
            store_id=store_id,
            run_type=run_type,
            status="running",
            metadata_json=metadata_json,
        )

    finish_called = []

    def fake_finish_run(session, run_id, **kwargs):
        finish_called.append(run_id)
        return SimpleNamespace(id=run_id, metadata_json={})

    upsert_calls = []

    def fake_upsert_product(session, *, product_url=None, **kwargs):
        upsert_calls.append(product_url)
        return (SimpleNamespace(id=1), True, False)

    monkeypatch.setattr(product_sync_service, "start_run", fake_start_run)
    monkeypatch.setattr(product_sync_service, "finish_run", fake_finish_run)
    monkeypatch.setattr(product_sync_service, "fail_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(product_sync_service, "update_counters", lambda *args, **kwargs: None)
    monkeypatch.setattr(product_sync_service, "list_products_by_category", lambda session, category_id: [])
    monkeypatch.setattr(product_sync_service, "upsert_product", fake_upsert_product)
    monkeypatch.setattr(product_sync_service, "resolve_adapter_for_store", lambda store: StubAdapter())
    monkeypatch.setattr(ProductSyncService, "_get_category", lambda self, category_id: category)

    service = ProductSyncService(session=None)
    result = service.sync_category_products(category.id)

    assert len(upsert_calls) == 1
    expected_url = "https://example.com/p/123"
    assert upsert_calls[0] == expected_url
    assert result["summary"]["skipped_invalid_products"] == 2
    assert result["summary"]["skipped_missing_url"] == 2
    counts = result["summary"]["validation_error_counts"]
    assert counts.get("missing_product_url") == 2
    sample = result["summary"]["validation_errors_sample"]
    assert len(sample) == 2
    assert sample[0]["type"] == "missing_product_url"
    assert result["scrape_run"].metadata_json["skipped_invalid_products"] == 2
    assert result["scrape_run"].metadata_json["validation_error_counts"]["missing_product_url"] == 2


def test_normalize_uses_explicit_price_numeric():
    service = ProductSyncService(session=None)
    item = {"name": "ExplicitPrice", "price": 123.45, "price_raw": "$999.00", "currency": None}
    normalized = service._normalize_product_dto(item, None)
    assert normalized["price"] == 123.45


def test_normalize_parses_price_raw_when_no_explicit(monkeypatch):
    # Подменим parse_price_value чтобы вернуть ожидаемые значения
    monkeypatch.setattr(product_sync_service, "parse_price_value", lambda raw: (99.0, "EUR"))
    service = ProductSyncService(session=None)
    item = {"name": "FromRaw", "price_raw": "€99.00"}
    normalized = service._normalize_product_dto(item, None)
    assert normalized["price"] == 99.0
    assert normalized["currency"] == "EUR"


def test_currency_explicit_overrides_parsed(monkeypatch):
    monkeypatch.setattr(product_sync_service, "parse_price_value", lambda raw: (10.0, "USD"))
    service = ProductSyncService(session=None)
    item = {"name": "CurrencyExplicit", "price_raw": "$10.00", "currency": "GBP"}
    normalized = service._normalize_product_dto(item, None)
    assert normalized["price"] == 10.0
    assert normalized["currency"] == "GBP"


def test_source_url_preferred_and_normalized():
    service = ProductSyncService(session=None)
    category_url = "https://example.com/cat/"
    # source_url is relative and should be joined with category_url
    item = {"name": "WithSource", "source_url": "/s/path", "source_site": "https://legacy.example.com"}
    normalized = service._normalize_product_dto(item, category_url)
    assert normalized["source_url"] == "https://example.com/s/path"

    # object-style DTO should также work
    obj = SimpleNamespace(name="Obj", price=5)
    normalized_obj = service._normalize_product_dto(obj, None)
    assert normalized_obj["price"] == 5
