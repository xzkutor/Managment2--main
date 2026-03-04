from bs4 import BeautifulSoup
from pricewatch.shops.prohockey.adapter import ProHockeyAdapter


class DummyResp:
    def __init__(self, content_bytes):
        self.content = content_bytes


class DummyClient:
    def __init__(self, html):
        self.session = None
        self._resp = DummyResp(html.encode('utf-8'))

    def safe_get(self, url, session=None):
        return self._resp


def test_prohockey_get_categories_dropdown_and_nav_link():
    html = '''
    <html>
      <body>
        <a class="dropdown-item" href="/catalog/ice"> <span>Ice</span> </a>
        <a class="nav-link" href="/catalog/sticks"> <span>Sticks</span> </a>
        <a href="/not-catalog/skip">Skip</a>
      </body>
    </html>
    '''
    client = DummyClient(html)
    adapter = ProHockeyAdapter()
    cats = adapter.get_categories(client)
    names = {c['name'] for c in cats}
    assert 'Ice' in names
    assert 'Sticks' in names


