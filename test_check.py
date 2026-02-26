from parser import create_session, fetch_main_site_products, fetch_other_site_products, product_exists_on_main, get_prohockey_categories

import logging

# quiet urllib3 debug noise so counts are easier to read
logging.getLogger('urllib3').setLevel(logging.WARNING)

import parser
# speed up tests by removing artificial delays
parser.MIN_DELAY = 0
parser.MAX_DELAY = 0

# silence the verbose safe_get during tests
original_safe_get = parser.safe_get

def quiet_get(session, url, method='GET', **kwargs):
    try:
        return session.request(method, url, timeout=15, allow_redirects=True, **kwargs)
    except Exception:
        return None

parser.safe_get = quiet_get

session = create_session()

print('discovering categories from prohockey:')
cats = get_prohockey_categories(session)
print(cats)

# grab any category from reference site for demonstration purposes
cat = cats[0] if cats else ''

# fetch only the specified category from reference (should succeed)
main = fetch_main_site_products(session, [cat])
print('main count', len(main), '(category='+cat+')')

# ---------------------------
# hockeyshans tests - these sites do not necessarily share the same
# category keywords as prohockey, so we do *not* supply the category filter.
# instead we just verify that products are returned at all.
others = fetch_other_site_products(session, 'hockeyshans.com.ua/category/2', category=None)
print('others count (explicit category URL)', len(others))
assert len(others) > 0, "expected some products from explicit hockeyshans category"
# make sure we extracted at least one name/url
assert any(p.get('name') for p in others), "expected at least one name"
assert any(p.get('url') for p in others), "expected at least one url"
print('sample others:', others[:5])

others2 = fetch_other_site_products(session, 'hockeyshans.com.ua', category=None)
print('others count (domain only)', len(others2))
assert len(others2) > 0, "expected some products when scraping hockeyshans root"
assert any(p.get('name') for p in others2), "expected at least one name"
assert any(p.get('url') for p in others2), "expected at least one url"
print('sample others2:', others2[:5])

