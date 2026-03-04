from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup

from pricewatch.core.registry import get_registry
from pricewatch.core.reference_service import ReferenceCatalogBuilder
from pricewatch.core.generic_adapter import GenericAdapter
from pricewatch.core.normalize import product_exists_on_main, parse_price
from __init__ import default_client

app = Flask(__name__)
CORS(app)

# ensure Flask's jsonify emits actual UTF-8 (not ascii-escaped)
app.json.ensure_ascii = False

registry = get_registry()


@app.after_request
def set_response_charset(response):
    """Ensure responses include charset=utf-8 in Content-Type for API/HTML responses.

    This keeps behavior explicit for clients that expect a charset header.
    Only add charset when it's not already present.
    """
    try:
        content_type = response.headers.get('Content-Type', '')
        if 'charset' not in content_type.lower():
            mimetype = response.mimetype or ''
            if mimetype in ('application/json', 'text/html', 'application/javascript'):
                response.headers['Content-Type'] = f"{mimetype}; charset=utf-8"
    except Exception as e:
        # preserve existing behavior on failure, but log for debugging
        print(f"set_response_charset failed: {e}")
    return response


def _item_to_dict(item):
    price_value, currency = parse_price(item.price_raw)
    return {
        "name": item.name,
        "price": price_value,
        "currency": currency,
        "url": item.url,
        "source_site": item.source_site,
    }


def _decode_escapes(s):
    # only attempt decode when it looks like an escaped unicode sequence
    if not isinstance(s, str) or "\\u" not in s:
        return s
    try:
        return s.encode('utf-8').decode('unicode_escape')
    except Exception:
        return s

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def scrape():
    # keep the old scrape behaviour for backwards compatibility
    # (it still powers the previous comparison UI if needed)
    return "not implemented", 501

@app.route('/api/adapters', methods=['GET'])
def adapters_list():
    """Return the list of available adapters and their supported domains.

    The frontend uses this to show which sites are supported for scraping.
    """
    adapters = []
    for adapter in registry.adapters:
        # exclude the reference adapter from the returned list
        if getattr(adapter, 'is_reference', False):
            continue
        adapters.append({
            'name': adapter.name,
            'domains': adapter.domains,
        })
    return jsonify({'adapters': adapters})


@app.route('/api/categories', methods=['GET'])
def categories_list():
    """Return the list of available reference-site categories.

    The frontend uses this to populate its category dropdown dynamically.
    """
    reference = registry.reference_adapter()
    cats = reference.get_categories(default_client)
    return jsonify({'categories': cats})


@app.route('/api/check', methods=['POST'])
def check_missing():
    print("=" * 50)
    print("📨 Received check request")
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    data = request.get_json()
    urls = data.get('urls', [])
    category = data.get('category') or None  # convert empty string to None
    if not urls:
        return jsonify({'error': 'Не указаны URL'}), 400

    reference = registry.reference_adapter()
    builder = ReferenceCatalogBuilder(reference, default_client)
    main_products = builder.build([category] if category else None)
    print(f"Main site items: {len(main_products)} (category={category})")

    missing = []
    scanned = 0
    for url in urls:
        if not url.startswith('http'):
            url = 'https://' + url
        print(f"checking other site: {url}")
        adapter = registry.for_url(url) or GenericAdapter()
        print(f"  -> adapter: {adapter.name}")
        others = adapter.scrape_url(default_client, url)
        scanned += len(others)
        for p in others:
            if not product_exists_on_main(p.name):
                entry = _item_to_dict(p)
                entry['status'] = 'нема такого товару'
                missing.append(entry)
            else:
                print(f"  -> found on main: {p.name}")

    return jsonify({
        'missing': missing,
        'total': len(missing),
        'total_urls': len(urls),
        'scanned': scanned,
    })

@app.route('/api/parse-example', methods=['POST'])
def parse_example():
    """Парсит пример товаров для демонстрации"""
    data = request.json
    html_content = data.get('html', '')
    
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    for row in soup.find_all('tr')[1:]:  # Пропускаем header
        cols = row.find_all('td')
        if len(cols) >= 3:
            products.append({
                'article': cols[0].get_text(strip=True),
                'name': cols[1].get_text(strip=True),
                'model': cols[2].get_text(strip=True),
                'source_domain': 'example'
            })
    
    return jsonify({'products': products})

@app.route('/api/adapters/<adapter_name>/categories', methods=['GET'])
def adapter_categories(adapter_name):
    """Return categories produced by the named adapter (by adapter.name).

    If adapter is not found, return 404. The adapter receives the shared
    `default_client` instance and must support `get_categories(client)`.
    """
    # find adapter by name
    adapter = None
    for a in registry.adapters:
        if a.name == adapter_name:
            adapter = a
            break
    if not adapter:
        return jsonify({'error': 'adapter not found'}), 404

    print(f"Fetching categories for adapter: {adapter.name}")
    cats = adapter.get_categories(default_client)

    # decode any escaped unicode sequences returned by adapters (e.g. '\\u041f...')
    if isinstance(cats, list):
        for c in cats:
            if isinstance(c, dict) and 'name' in c and isinstance(c['name'], str):
                c['name'] = _decode_escapes(c['name'])

    return jsonify({'categories': cats})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
