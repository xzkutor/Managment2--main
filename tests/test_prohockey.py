from bs4 import BeautifulSoup

from pricewatch.shops.prohockey.adapter import ProHockeyAdapter


def test_get_next_page_variants():
    adapter = ProHockeyAdapter()

    html_with_next = '''
    <ul class="pagination">
      <li><a href="/page/1">1</a></li>
      <li><a href="/page/2">Вперед</a></li>
    </ul>
    '''
    assert adapter.get_next_page(BeautifulSoup(html_with_next, 'html.parser')) == '/page/2'

    html_disabled = '''
    <ul class="pagination">
      <li><a href="/page/1">1</a></li>
      <li class="disabled"><a href="/page/2">Вперед</a></li>
    </ul>
    '''
    assert adapter.get_next_page(BeautifulSoup(html_disabled, 'html.parser')) is None

    html_no_next = '''
    <ul class="pagination">
      <li><a href="/page/1">1</a></li>
      <li><a href="/page/2">2</a></li>
    </ul>
    '''
    assert adapter.get_next_page(BeautifulSoup(html_no_next, 'html.parser')) is None

    html_variant = '''
    <ul class="pagination">
      <li><a href="/page/3">Вперёд</a></li>
    </ul>
    '''
    assert adapter.get_next_page(BeautifulSoup(html_variant, 'html.parser')) == '/page/3'


def test_scrape_category_multiple_pages():
    # Fake client that returns two pages: /catalog (page1) and /page/2 (page2)
    class FakeResp:
        def __init__(self, html):
            self.content = html.encode('utf-8')

    class FakeClient:
        def __init__(self, pages):
            self.pages = pages
            self.session = None

        def safe_get(self, url, session=None):
            # simple matching based on URL suffix
            if url.endswith('/catalog') or url.endswith('/catalog/') or url.endswith('https://prohockey.com.ua/catalog'):
                return FakeResp(self.pages['/catalog'])
            if url.endswith('/page/2') or url.endswith('/catalog/page/2'):
                return FakeResp(self.pages['/page/2'])
            return None

    # Page HTML uses selectors expected by adapter
    page1 = '''
    <html><body>
    <div class="product-item">
      <h4 class="card-title">Product 1</h4>
      <a class="product-link" href="/p1">details</a>
      <div class="price-line">100 грн</div>
    </div>
    <ul class="pagination">
      <li><a href="/page/1">1</a></li>
      <li><a href="/page/2">Вперед</a></li>
    </ul>
    </body></html>
    '''

    page2 = '''
    <html><body>
    <div class="product-item">
      <h4 class="card-title">Product 2</h4>
      <a class="product-link" href="/p2">details</a>
      <div class="price-line">200 грн</div>
    </div>
    <ul class="pagination">
      <li class="disabled"><a href="/page/3">Вперед</a></li>
    </ul>
    </body></html>
    '''

    pages = {'/catalog': page1, '/page/2': page2}
    client = FakeClient(pages)
    adapter = ProHockeyAdapter()

    items = adapter.scrape_category(client, None)
    # Expect both products collected from two pages
    assert isinstance(items, list)
    assert len(items) == 2

    names = [i.name for i in items]
    assert 'Product 1' in names
    assert 'Product 2' in names

    urls = [i.url for i in items]
    assert any('/p1' in u for u in urls)
    assert any('/p2' in u for u in urls)
