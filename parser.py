import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time
import random
import json
import sys
import http.client as http_client
import logging
from rapidfuzz import fuzz
import csv
import re

# Global storage for main-site normalized titles
MAIN_NORMALIZED = []

# Enable debug logging for HTTP requests (can be lowered in production)
# set debuglevel to 0 to suppress low-level HTTP chatter
http_client.HTTPConnection.debuglevel = 0
logging.basicConfig()
# default to INFO; individual callers/tests may raise this level if needed
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# helper for creating a session with retries and custom UA

def create_session():
    sess = requests.Session()
    sess.headers.update(HEADERS)
    # retry adapter
    from requests.adapters import HTTPAdapter
    from urllib3.util import Retry
    retries = Retry(total=3, backoff_factor=0.5,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET", "POST"])
    adapter = HTTPAdapter(max_retries=retries)
    sess.mount('http://', adapter)
    sess.mount('https://', adapter)
    return sess

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'uk-UA,uk;q=0.9,en;q=0.8',
    'Referer': 'https://www.google.com/',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0'
}

# Delay between requests (seconds) - randomized between MIN_DELAY and MAX_DELAY
# Set FAST_MODE=True to disable sleeping and speed up scraping (useful for
# local analysis or trusted sites).  In production you may want some delay to
# avoid triggering anti-scraping protections.
MIN_DELAY = 1.0
MAX_DELAY = 2.0
FAST_MODE = os.getenv('PARSER_FAST', '').lower() in ('1', 'true', 'yes')
# Maximum number of pages to fetch when paginating. ``None`` means no limit.
# In fast mode a default of 5 is applied to avoid long loops.
PAGE_LIMIT = 4


def safe_get(session, url, method='GET', **kwargs):
    """Perform a GET request with logging, timeout and optional delay.
    Returns Response or None.
    """
    print(f"--> {method} {url}")
    print(f"    headers: {session.headers}")
    if 'params' in kwargs:
        print(f"    params: {kwargs['params']}")
    if 'data' in kwargs or 'json' in kwargs:
        print(f"    body: {kwargs.get('data') or kwargs.get('json')}")
    try:
        resp = session.request(method, url, timeout=15, allow_redirects=True, **kwargs)
        print(f"<-- status {resp.status_code} for {url}")
        if resp.status_code in (400, 403, 429):
            txt = resp.text[:1000].replace('\n',' ')
            print(f"    response text: {txt}")
            return None
        # polite randomized delay after successful request to avoid being blocked
        if not FAST_MODE:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            time.sleep(delay)
        return resp
    except Exception as e:
        print(f"Request failed for {url}: {e}")
        return None


def extract_text(el):
    return el.get_text(strip=True) if el else ''


def parse_price(price_str):
    if not price_str:
        return '', ''
    # simple regex: number part and currency part
    m = re.search(r"([\d\s,\.]+)\s*([^\d\s]+)", price_str)
    if m:
        value = m.group(1).strip()
        curr = m.group(2).strip()
        return value, curr
    return price_str.strip(), ''


def normalize_title(title: str) -> str:
    t = title.lower()
    # remove parenthetical content
    t = re.sub(r"\([^)]*\)", "", t)
    # remove special characters except spaces and alphanumerics
    t = re.sub(r"[^a-z0-9\s]", "", t)
    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def product_exists_on_main(title: str, threshold: float = 85.0) -> bool:
    norm = normalize_title(title)
    for existing in MAIN_NORMALIZED:
        if norm == existing:
            return True
        score = fuzz.ratio(norm, existing)
        if score >= threshold:
            return True
    return False


def extract_products_from_json(obj, base_url):
    """Recursively search a JSON-like object for product lists.
    Returns list of dicts with keys name, price, url if found, otherwise empty list.
    """
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            # if we have a list of dicts, maybe it's products
            if isinstance(v, list) and v and isinstance(v[0], dict):
                # look for typical product keys
                sample = v[0]
                if any(key in sample for key in ('name', 'title', 'price', 'url', 'link')):
                    for item in v:
                        name = item.get('name') or item.get('title', '')
                        price = item.get('price', '')
                        url = normalize_link(base_url, item.get('url') or item.get('link') or '')
                        results.append({'name': name, 'price': price, 'url': url})
                    return results
            # otherwise descend
            sub = extract_products_from_json(v, base_url)
            if sub:
                results.extend(sub)
    elif isinstance(obj, list):
        for el in obj:
            sub = extract_products_from_json(el, base_url)
            if sub:
                results.extend(sub)
    return results


def scan_for_json_in_html(soup, base_url):
    """Look inside <script> tags for inline JSON containing product data."""
    import re

    def find_json_strings(text):
        """Return list of balanced JSON substrings from text."""
        results = []
        stack = []
        start = None
        for i, ch in enumerate(text):
            if ch in '{[':
                if not stack:
                    start = i
                stack.append(ch)
            elif ch in '}]' and stack:
                opener = stack.pop()
                if not stack and start is not None:
                    results.append(text[start:i+1])
                    start = None
        return results

    for script in soup.find_all('script'):
        text = script.string or script.get_text()
        if not text:
            continue
        # first try to extract JSON payloads directly
        for candidate in find_json_strings(text):
            try:
                payload = json.loads(candidate)
                products = extract_products_from_json(payload, base_url)
                if products:
                    return products
            except Exception:
                pass
    return None


def find_first(soup, selectors):
    for sel in selectors:
        elems = soup.select(sel)
        if elems:
            return elems
    return []


def normalize_link(base, link):
    if not link:
        return ''
    return urljoin(base, link)


def paginate_and_collect(base_url, session, item_selectors, name_selectors, price_selectors, link_selectors):
    """
    Attempts to paginate using a pattern. It will try to detect a working pagination scheme:
    - If base_url already contains "page=", it will replace that value.
    - Otherwise it will try '?page=N' or '/page/N/' styles.
    Stops when a page returns no items.

    This function now also checks for JSON/API responses. If the response
    content-type is JSON or if inline JS contains JSON data, it'll attempt
    to extract products from it instead of parsing HTML.
    """
    parsed = urlparse(base_url)
    base_without_query = base_url.split('?')[0]

    # candidate patterns (functions that given n -> url)
    def pattern_replace(n):
        if 'page=' in base_url:
            # replace existing page parameter
            # naive replace: find page=NUMBER and replace
            import re
            return re.sub(r'(page=)\d+', r'\1{}'.format(n), base_url)
        return None

    def pattern_query(n):
        sep = '&' if parsed.query else '?'
        return f"{base_without_query}{sep}page={n}"

    def pattern_path(n):
        return f"{base_without_query.rstrip('/')}/page/{n}/"

    patterns = [pattern_replace, pattern_query, pattern_path]

    def check_for_json(resp, url_for_base):
        # parse JSON response if applicable
        ctype = resp.headers.get('Content-Type', '')
        if 'application/json' in ctype or resp.text.strip().startswith(('{', '[')):
            try:
                data = resp.json()
            except Exception:
                # maybe text looks json-like but isn't
                try:
                    data = json.loads(resp.text)
                except Exception:
                    return []
            products = extract_products_from_json(data, url_for_base)
            if products:
                print(f"Extracted {len(products)} items from JSON at {url_for_base}")
                return products
        return []

    # helper to locate API endpoints in script tags and try them
    def find_and_try_api(soup):
        import re
        urls = set()
        for script in soup.find_all('script'):
            txt = script.string or script.get_text()
            if not txt:
                continue
            for match in re.findall(r"fetch\(['\"]([^'\"]+)['\"]", txt):
                urls.add(match)
            for match in re.findall(r"axios\.get\(['\"]([^'\"]+)['\"]", txt):
                urls.add(match)
            for match in re.findall(r"\$\.getJSON\(['\"]([^'\"]+)['\"]", txt):
                urls.add(match)
        for u in urls:
            full = urljoin(base_url, u)
            resp = safe_get(session, full)
            if resp:
                extracted = check_for_json(resp, full)
                if extracted:
                    return extracted
        return []

    # Try to find which pattern works for page 1 (or no pagination)
    chosen = None
    for pat in patterns:
        url1 = pat(1)
        if not url1:
            continue
        resp = safe_get(session, url1)
        if not resp:
            continue
        # first check for API/JSON response
        products = check_for_json(resp, url1)
        if products:
            return products

        soup = BeautifulSoup(resp.content, 'html.parser')
        items = find_first(soup, item_selectors)
        if items:
            chosen = pat
            print(f"Found {len(items)} items with selectors at {url1}")
            break

    # If none patterns returned items, try the base url without pagination
    if chosen is None:
        print(f"Trying base URL without pagination: {base_url}")
        resp = safe_get(session, base_url)
        if not resp:
            print(f"Failed to get response from {base_url}")
            return []
        # check JSON first
        json_products = check_for_json(resp, base_url)
        if json_products:
            return json_products

        soup = BeautifulSoup(resp.content, 'html.parser')
        items = find_first(soup, item_selectors)
        if items:
            chosen = lambda n: base_url if n == 1 else None
            print(f"Found {len(items)} items at base URL")
        else:
            # nothing found with configured selectors — try JSON inside HTML or API endpoints
            print(f"No items found with selectors: {item_selectors}")
            # Print an ASCII-safe preview to avoid console encoding errors
            preview = soup.prettify()[:2000].encode('ascii', errors='replace').decode('ascii')
            print(f"HTML preview: {preview}")

            # attempt to parse inline JSON
            inline = scan_for_json_in_html(soup, base_url)
            if inline:
                return inline

            # try to detect api urls in scripts
            api_results = find_and_try_api(soup)
            if api_results:
                return api_results

            print("Attempting fallback heuristic to locate product-like blocks...")
            candidates = []
            # look for links and try to climb up to a container that may represent a product
            import re
            product_class_keywords = re.compile(r'product|prod|card|catalog|tov(ar)?|goods|item|listing', re.I)
            price_pattern = re.compile(r'(\d+[\s\u00A0]?\d{0,3}[,.]?\d{0,2})\s*(₴|UAH|грн|грн\.|uah|\$)', re.I)

            for a in soup.select('a[href]'):
                href = a.get('href', '').strip()
                if not href or href.startswith('#') or href.startswith('tel:') or href.startswith('mailto:'):
                    continue

                # Skip links that point to site root or javascript
                if href in ('/', '') or href.lower().startswith('javascript:'):
                    continue

                parent = a
                found = False
                for _ in range(4):
                    # check class names for product-like keywords
                    classes = parent.get('class') or []
                    cls_str = ' '.join(classes) if isinstance(classes, (list, tuple)) else str(classes)
                    text = parent.get_text(separator=' ', strip=True)

                    has_price = bool(price_pattern.search(text))
                    has_img = bool(parent.select_one('img'))
                    has_product_class = bool(product_class_keywords.search(cls_str))

                    # heuristics for href looking like a product page
                    is_product_href = bool(re.search(r'/(product|products|item|tov(ar)?|goods|p/|sku|sku-|product-)|-[0-9]{2,}$', href, re.I))

                    # require two signals to reduce false positives:
                    # (img or price) + (product-class or product-like href)
                    positive_signals = 0
                    if has_img or has_price:
                        positive_signals += 1
                    if has_product_class or is_product_href:
                        positive_signals += 1

                    if positive_signals >= 2:
                        candidates.append(parent)
                        found = True
                        break

                    if parent.parent is None:
                        break
                    parent = parent.parent

                if found:
                    continue

            # deduplicate and limit candidates
            seen = set()
            items = []
            for c in candidates:
                classes = c.get('class')
                if isinstance(classes, list):
                    classes = tuple(classes)
                key = (c.name, classes, c.get_text()[:200])
                if key in seen:
                    continue
                seen.add(key)
                items.append(c)

            if items:
                print(f"Fallback found {len(items)} candidate items")
                # Build results directly from fallback items (no pagination)
                results = []
                for item in items:
                    # try to extract name, price, link similarly to normal flow
                    name_el = None
                    for sel in name_selectors:
                        el = item.select_one(sel)
                        if el and el.get_text(strip=True):
                            name_el = el
                            break

                    price_el = None
                    for sel in price_selectors:
                        el = item.select_one(sel)
                        if el and el.get_text(strip=True):
                            price_el = el
                            break

                    link_el = None
                    for sel in link_selectors:
                        el = item.select_one(sel)
                        if el and el.has_attr('href'):
                            link_el = el
                            break

                    # if selectors failed to pick up a title, try attributes
                    name = extract_text(name_el) if name_el else ''
                    if not name and item.name == 'a' and item.has_attr('title'):
                        name = item['title']
                    if not name:
                        # maybe the container has an image alt text
                        img = item.select_one('img[alt]')
                        if img:
                            name = img.get('alt', '')

                    price = extract_text(price_el) if price_el else ''
                    url = normalize_link(base_url, link_el['href'] if link_el else '')

                    if not price:
                        price_text_candidates = item.select('*')
                        for cand in price_text_candidates:
                            txt = cand.get_text(strip=True)
                            if any(ch.isdigit() for ch in txt) and ('UAH' in txt or '₴' in txt or ' грн' in txt or 'грн' in txt or '$' in txt):
                                price = txt
                                break

                    results.append({'name': name, 'price': price, 'url': url})

                return results
            else:
                print("Fallback failed — no candidate product blocks found")
                return []

    results = []
    page = 1
    empty_page_count = 0  # count consecutive pages with no valid items
    # determine effective page limit
    limit = PAGE_LIMIT
    if FAST_MODE and limit is None:
        limit = 5
    while True:
        if limit and page > limit:
            print(f"page limit {limit} reached, stopping pagination")
            break
        target_url = chosen(page)
        if not target_url:
            break

        print(f"Fetching: {target_url}")
        resp = safe_get(session, target_url)
        if not resp:
            break

        soup = BeautifulSoup(resp.content, 'html.parser')
        items = find_first(soup, item_selectors)
        if not items:
            print(f"No items found on page {page} (url: {target_url}), stopping pagination.")
            break

        # check if items are actually valid (have content) or just markup placeholders
        page_had_valid_items = False
        for item in items:
            # try to extract name, price, link
            name_el = None
            for sel in name_selectors:
                el = item.select_one(sel)
                if el and el.get_text(strip=True):
                    name_el = el
                    break
            if not name_el and item.name == 'a' and item.has_attr('title'):
                name_el = item
            if not name_el:
                img = item.select_one('img[alt]')
                if img:
                    name_el = img

            link_el = None
            for sel in link_selectors:
                el = item.select_one(sel)
                if el and el.has_attr('href'):
                    link_el = el
                    break

            # if we have a name or link, this is a valid item
            if (name_el and name_el.get_text(strip=True)) or (link_el and link_el.get('href')):
                page_had_valid_items = True
                break

        if not page_had_valid_items:
            empty_page_count += 1
            print(f"page {page} has no valid items ({empty_page_count}/3 empty)")
            if empty_page_count >= 3:
                print(f"stopping pagination after 3 consecutive empty pages")
                break
            page += 1
            continue  # skip to next page, don't add items from this one
        else:
            empty_page_count = 0

        for item in items:
            # name
            name_el = None
            for sel in name_selectors:
                el = item.select_one(sel)
                if el and el.get_text(strip=True):
                    name_el = el
                    break

            # price
            price_el = None
            for sel in price_selectors:
                el = item.select_one(sel)
                if el and el.get_text(strip=True):
                    price_el = el
                    break

            # link
            link_el = None
            for sel in link_selectors:
                el = item.select_one(sel)
                if el and el.has_attr('href'):
                    link_el = el
                    break

            name = extract_text(name_el) if name_el else ''
            price = extract_text(price_el) if price_el else ''
            url = normalize_link(target_url, link_el['href'] if link_el else '')

            # Some product lists don't include price on the item; try to find global price within item
            if not price:
                # try any descendant that contains digits and currency symbols
                price_text_candidates = item.select('*')
                for cand in price_text_candidates:
                    txt = cand.get_text(strip=True)
                    if any(ch.isdigit() for ch in txt) and ('UAH' in txt or '₴' in txt or ' грн' in txt or 'грн' in txt or '$' in txt):
                        price = txt
                        break

            results.append({'name': name, 'price': price, 'url': url})

        page += 1

    return results


# Specific site parsers

def scrape_prohockey(session, category='sticks-sr'):
    """
    Scrape products from prohockey.com.ua
    This function already supports API/JSON detection via paginate_and_collect.

    When a non-empty *category* is supplied we also attempt a quick
    discovery step: the home page is scanned for any anchor whose href or text
    contains the category keyword. If such a link is found it is used instead
    of the naive ``/catalog/{category}`` URL. This mirrors the behaviour added
    for other sites and ensures that changing category paths on prohockey will
    not break the scraper.
    """
    # build default URL but allow discovery to override it
    base = f'https://prohockey.com.ua/catalog/{category}'
    if category:
        found = find_category_page(session, 'https://prohockey.com.ua', category)
        if found and found != base:
            print(f"  -> using discovered reference category page: {found}")
            base = found

    # The site uses a variety of selectors depending on page structure.
    # Try both modern class-based selectors and fallback IDs/data attributes.
    item_selectors = [
        'div[class*="product"][class*="item"]',  # generic product-item classes
        'div.card',  # Bootstrap cards
        'div.row > div[class*="col"] > div[class*="product"]',  # grid layout
        'article.product',
        'div[data-product-id]',  # data attribute selector
        'div.catalog-item',
        'div.product',
        'div.item',
        'div.tz-item',
        'li.product',
        'div.catalog__item',
        '.catalog-card',
        '.product-list-item'
    ]

    name_selectors = [
        'a.product-title',
        'a.catalog-item__title',
        'h3 a',
        'h2 a',
        '.title a',
        '.product-name a',
        'h1',
        'h2',
        'h3',
        'h4',
        'a'
    ]

    price_selectors = [
        '.price .value',
        '.price',
        '.catalog-item__price',
        '.woocommerce-Price-amount',
        '.tov_price',
        '.product-price',
        '[class*="price"]'
    ]

    link_selectors = [
        'a.product-title',
        '.catalog-item__title a',
        'h3 a',
        'a'
    ]

    raw = paginate_and_collect(base, session, item_selectors, name_selectors, price_selectors, link_selectors)
    results = []
    for r in raw:
        results.append({
            'site': 'prohockey.com.ua',
            'name': r.get('name', ''),
            'price': r.get('price', ''),
            'url': r.get('url', '')
        })
    return results


def scrape_hockeyshans(session, category='2'):
    """
    Scrape products from hockeyshans.com.ua
    
    Args:
        session: requests.Session object
        category: category ID (e.g., '2')
    """
    base = f'https://hockeyshans.com.ua/category/{category}'

    # the site uses a carousel of "thumbnail" elements; each card contains
    # an <a> with the image/title and a nested <div class="caption"> with an
    # <h5> name and price links in a .btn-group. using these selectors avoids
    # falling back to the generic heuristic that was returning empty items.
    item_selectors = [
        'div.thumbnail',
        'li.span2_4',
        'div.caption'
    ]

    name_selectors = [
        'div.capt-title h5',
        'div.caption h5',
        'h5',
        'a[title]',
        'img[alt]'
    ]

    price_selectors = [
        'div.btn-group',
        '.btn-usdprice',
        '.btn-primary',
        '.price',
        '.amount'
    ]

    link_selectors = [
        'a[href^="/item/"]',
        'a'
    ]

    raw = paginate_and_collect(base, session, item_selectors, name_selectors, price_selectors, link_selectors)
    results = []
    for r in raw:
        results.append({
            'site': 'hockeyshans.com.ua',
            'name': r.get('name', ''),
            'price': r.get('price', ''),
            'url': r.get('url', '')
        })
    return results


def get_prohockey_categories(session):
    """Return a list of category slugs observed on the prohockey homepage.

    The function scans anchor tags for paths containing "/catalog/" and
    extracts the fragment following that segment.  The returned list is
    de-duplicated and sorted.
    """
    base = 'https://prohockey.com.ua'
    resp = safe_get(session, base)
    if not resp:
        return []
    soup = BeautifulSoup(resp.content, 'html.parser')
    cats = set()
    for a in soup.select('a[href]'):
        href = a['href']
        if '/catalog/' in href:
            parsed = urlparse(href)
            path = parsed.path
            parts = path.split('/catalog/')
            if len(parts) > 1:
                slug = parts[1].strip('/')
                if slug:
                    cats.add(slug)
    return sorted(cats)


def fetch_main_site_products(session, categories=None):
    """Return list of products from the reference site (prohockey) suitable
    for matching. Each item is dict with name, price, currency, url, source_site.

    If *categories* is ``None`` the set of available categories is pulled
    dynamically from the prohockey homepage via :func:`get_prohockey_categories`.
    """
    if categories is None:
        categories = get_prohockey_categories(session)
        print(f"fetch_main_site_products: discovered {len(categories)} categories")
    results = []
    for cat in categories:
        print(f"fetch_main_site_products: category={cat}")
        items = scrape_prohockey(session, category=cat)
        for it in items:
            name = it.get('name','')
            price = it.get('price','')
            val, curr = parse_price(price)
            url = it.get('url','')
            domain = urlparse(url).netloc or 'prohockey.com.ua'
            results.append({
                'name': name,
                'price': val,
                'currency': curr,
                'url': url,
                'source_site': domain,
            })
    # populate normalization list for quick membership test
    MAIN_NORMALIZED.clear()
    for r in results:
        MAIN_NORMALIZED.append(normalize_title(r['name']))
    return results



# helper used when a category keyword is supplied for a non‑reference site.
# we attempt to discover a page on the target site that corresponds to the
# requested category by looking for links whose href or text contains the
# keyword. if found, we will scrape that page instead of the originally
# provided URL.
def find_category_page(session, base_url, category):
    """Try to locate a category-specific URL on *base_url* site.

    Returns an absolute URL pointing to a page whose anchor href or link text
    contains *category*. If nothing obvious is found it returns ``None``.
    The search is confined to links on the same domain as ``base_url``.
    """
    from urllib.parse import urlparse, urljoin

    parsed = urlparse(base_url)
    # ensure we always have a scheme and netloc
    scheme = parsed.scheme or 'https'
    domain = f"{scheme}://{parsed.netloc}"

    try_urls = [base_url]
    # also try the homepage in case the user supplied a deep link
    if base_url.rstrip('/') != domain.rstrip('/'):
        try_urls.append(domain)

    cat_lower = category.lower()
    for u in try_urls:
        resp = safe_get(session, u)
        if not resp:
            continue
        soup = BeautifulSoup(resp.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(" ", strip=True).lower()
            full = urljoin(domain, href)
            # only consider links that stay on the same host
            if parsed.netloc not in urlparse(full).netloc:
                continue
            if cat_lower in href.lower() or cat_lower in text:
                return full
    return None


def fetch_other_site_products(session, url, category=None):
    """Generic fetch for any other site URL. Returns list of product dicts.

    The *url* argument may be any reachable page on the target site. If
    *category* is specified we first look for a page on that site which
    appears to correspond to the category (by looking for anchors whose href
    or text contains the keyword). When such a page is found it becomes the
    base URL passed to :func:`paginate_and_collect`.

    After the raw items are collected we still apply a lightweight filter:
    any product whose name or link does not include the category string is
    discarded. This reduces noise when the two sites use a common vocabulary
    but the supplied URL could not be narrowed automatically.
    """
    print(f"fetch_other_site_products: {url} (category={category})")

    # domain-specific shortcuts ------------------------------------------------
    from urllib.parse import urlparse
    parsed = urlparse(url if url.startswith('http') else 'https://' + url)
    host = parsed.netloc.lower()
    if 'hockeyshans.com.ua' in host:
        # hockeyshans uses numeric category IDs; attempt to pull from path or
        # fall back to provided category. Scrape using the specialised
        # helper which knows the markup.
        cat = None
        m = re.search(r'/category/(\d+)', parsed.path)
        if m:
            cat = m.group(1)
        if category and not cat:
            # category may be an id string
            cat = str(category)
        print(f"  -> delegating to scrape_hockeyshans (category={cat})")
        return scrape_hockeyshans(session, category=cat or '2')

    base = url if url.startswith('http') else 'https://' + url
    if category:
        candidate = find_category_page(session, base, category)
        if candidate and candidate != base:
            print(f"  -> discovered category page on target site: {candidate}")
            base = candidate

    raw = paginate_and_collect(base, session,
                               item_selectors=[],
                               name_selectors=[],
                               price_selectors=[],
                               link_selectors=[])
    print(f"    paginate_and_collect returned {len(raw)} raw items")
    results = []
    for it in raw:
        name = it.get('name','')
        price = it.get('price','')
        val, curr = parse_price(price)
        link = it.get('url','')
        domain = urlparse(link or base).netloc
        entry = {
            'name': name,
            'price': val,
            'currency': curr,
            'url': link,
            'source_site': domain,
        }
        results.append(entry)

    if category:
        key = category.lower()
        before = len(results)
        results = [r for r in results if key in r.get('name','').lower() or key in (r.get('url','') or '').lower()]
        print(f"    filtered {before} -> {len(results)} items using category '{category}'")
    return results


def export_to_csv(results, filename='out.csv'):
    fieldnames = ['name','price','currency','source_site','product_url','status_on_main_site']
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                'name': r.get('name',''),
                'price': r.get('price',''),
                'currency': r.get('currency',''),
                'source_site': r.get('source_site',''),
                'product_url': r.get('url',''),
                'status_on_main_site': r.get('status',''),
            })

def print_table(results):
    """Simple columnar display to console."""
    if not results:
        print("(no rows)")
        return
    cols = ['name','price','currency','source_site','product_url','status']
    widths = {c: len(c) for c in cols}
    for r in results:
        for c in cols:
            widths[c] = max(widths[c], len(str(r.get(c,''))))
    # header
    hdr = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join('-'*widths[c] for c in cols)
    print(hdr)
    print(sep)
    for r in results:
        row = " | ".join(str(r.get(c,'')).ljust(widths[c]) for c in cols)
        print(row)


def main():
    session = create_session()

    # example list of other site URLs - can be loaded from file/config
    other_sites = [
        'hockeyshans.com.ua/category/2',
        # add more urls here
    ]

    main_products = fetch_main_site_products(session)
    print(f"main site has {len(main_products)} products")

    final = []
    for site in other_sites:
        others = fetch_other_site_products(session, site)
        for p in others:
            exists = product_exists_on_main(p['name'])
            if not exists:
                p['status'] = 'нема такого товару'
                final.append(p)
    if final:
        print("\nMissing products on main site:")
        print_table(final)
        export_to_csv(final, 'missing.csv')
        print(f"\nexported {len(final)} missing products to missing.csv")
    else:
        print("No missing products found")


if __name__ == '__main__':
    main()
