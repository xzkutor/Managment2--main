from pricewatch.core.generic_adapter import GenericAdapter


class DummyResp:
    def __init__(self, content_bytes):
        self.content = content_bytes


class DummyClient:
    def __init__(self, html):
        self.session = None
        self._resp = DummyResp(html.encode('utf-8'))

    def safe_get(self, url, session=None):
        # ignore url, always return preset response
        return self._resp


def test_generic_adapter_get_categories_discovers_links():
    html = '''
    <html>
      <body>
        <a href="/category/ice-hockey">Ice Hockey</a>
        <a href="/shop/products">Products</a>
        <a href="http://other.com/out">External</a>
        <a href="/some/long-name-link">This is a long descriptive link that should be ignored</a>
      </body>
    </html>
    '''
    client = DummyClient(html)
    adapter = GenericAdapter()
    # set a domain so the adapter will try to fetch a base URL
    adapter.domains = ("example.com",)

    cats = adapter.get_categories(client)
    # Expect to find at least two candidates (category and products), external should be filtered out
    urls = {c['url'] for c in cats}
    assert any('/category/ice-hockey' in u for u in urls)
    assert any('shop/products' in u or '/shop/products' in u for u in urls)


