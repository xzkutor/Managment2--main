from types import SimpleNamespace

from pricewatch.services.product_sync_service import ProductSyncService


def test_normalize_product_dto_numeric_price_preferred():
    svc = ProductSyncService(session=None)
    item = {
        'name': 'Prod A',
        'price': 123.45,
        'price_raw': '1 234 UAH',
        'currency': 'USD',
        'source_url': 'https://shop.example/p/1',
        'product_url': '/p/1',
    }
    norm = svc._normalize_product_dto(item, category_url='https://shop.example')
    assert norm['price'] == 123.45
    # explicit currency preferred
    assert norm['currency'] == 'USD'
    # source_url preserved
    assert norm['source_url'] == 'https://shop.example/p/1'
    # product_url normalized from product_url field
    assert norm['product_url'] == 'https://shop.example/p/1'


def test_normalize_product_dto_price_raw_fallback_and_currency_parsing():
    svc = ProductSyncService(session=None)
    item = {
        'name': 'Prod B',
        'price_raw': '1200 UAH',
        'url': '/p/2',
        'source_site': 'other',
    }
    norm = svc._normalize_product_dto(item, category_url='https://shop.example')
    assert norm['price'] == 1200.0
    assert norm['currency'].upper() == 'UAH'
    assert norm['product_url'] == 'https://shop.example/p/2'


def test_normalize_product_dto_explicit_currency_overrides_parsed():
    svc = ProductSyncService(session=None)
    item = {
        'name': 'Prod C',
        'price_raw': '1000 UAH',
        'currency': 'USD',
    }
    norm = svc._normalize_product_dto(item, category_url=None)
    assert norm['price'] == 1000.0
    assert norm['currency'] == 'USD'


def test_normalize_product_dto_source_url_preference_and_object_support():
    svc = ProductSyncService(session=None)
    obj = SimpleNamespace(
        name='Prod D',
        price_raw='500 EUR',
        source_url='https://source.example/p/5',
        url='/p/5'
    )
    norm = svc._normalize_product_dto(obj, category_url='https://shop.example')
    assert norm['source_url'] == 'https://source.example/p/5'
    assert norm['price'] == 500.0
    assert norm['product_url'] == 'https://shop.example/p/5'

