from bs4 import BeautifulSoup
from pricewatch.shops.hockeyshop.adapter import HockeyShopAdapter

adapter = HockeyShopAdapter()

fixtures = {
    'normal': '''
    <div class="cwc_pagination">
      <ul>
        <li><a href="/page/1">1</a></li>
        <li class="current_page">2</li>
        <li><a href="/page/3">3</a></li>
        <li><a href="/page/4">4</a></li>
      </ul>
    </div>
    ''',

    'last': '''
    <div class="cwc_pagination">
      <ul>
        <li><a href="/page/1">1</a></li>
        <li><a href="/page/2">2</a></li>
        <li class="current_page">3</li>
      </ul>
    </div>
    ''',

    'no_current': '''
    <div class="cwc_pagination">
      <ul>
        <li><a href="/page/1">1</a></li>
        <li><a href="/page/2">2</a></li>
        <li><a href="/page/3">3</a></li>
      </ul>
    </div>
    ''',

    'fallback_bottom_pagination': '''
    <div id="bottom-pagination">
      <ul class="pagination">
        <li><a href="/page/1">1</a></li>
        <li class="current_page">2</li>
        <li><a href="/page/3">3</a></li>
      </ul>
    </div>
    ''',
}

for name, html in fixtures.items():
    soup = BeautifulSoup(html, 'html.parser')
    res = adapter.get_next_page(soup)
    print(name, '->', res)

