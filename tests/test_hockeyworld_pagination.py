import pytest
from bs4 import BeautifulSoup

from pricewatch.shops.hockeyworld.adapter import HockeyWorldAdapter


def test_get_next_page_returns_href_when_last_anchor_title_vpered():
    html = '''
    <div id="bottom-pagination">
      <a href="/page/1" title="Назад">1</a>
      <a href="/page/2" title="Вперед">2</a>
    </div>
    '''
    soup = BeautifulSoup(html, 'html.parser')
    adapter = HockeyWorldAdapter()
    assert adapter.get_next_page(soup) == '/page/2'


def test_get_next_page_returns_none_when_no_vpered():
    html = '''
    <div id="bottom-pagination">
      <a href="/page/1" title="1">1</a>
      <a href="/page/2" title="2">2</a>
    </div>
    '''
    soup = BeautifulSoup(html, 'html.parser')
    adapter = HockeyWorldAdapter()
    assert adapter.get_next_page(soup) is None
