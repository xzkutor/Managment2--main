from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
from typing import cast

import logging

from pricewatch.core.registry import get_registry
from pricewatch.core.reference_service import ReferenceCatalogBuilder
from pricewatch.core.generic_adapter import GenericAdapter
from pricewatch.core.normalize import (
    product_exists_on_main,
    parse_price_value,
    normalize_title,
    MAIN_NORMALIZED,
)
from __init__ import default_client
from pricewatch.db import Base, init_engine, init_db, get_session_factory, get_scoped_session
from pricewatch.db.repositories import (
    list_stores,
    list_categories_by_store,
    list_products_by_category,
)
from pricewatch.services.category_sync_service import CategorySyncService
from pricewatch.services.product_sync_service import ProductSyncService
from pricewatch.services.mapping_service import MappingService
from pricewatch.services.scrape_history_service import ScrapeHistoryService
from pricewatch.services.store_service import StoreService
from pricewatch.db.models import Store

app = Flask(__name__)
CORS(app)
app.config.setdefault("ENABLE_ADMIN_SYNC", True)

# ensure Flask's jsonify emits actual UTF-8 (not ascii-escaped)
app.json.ensure_ascii = False

logger = logging.getLogger(__name__)

# Database: initialize engine and scoped session, auto-create tables unless disabled
engine = init_engine(app.config)
SessionFactory = get_session_factory(engine)
db_session = get_scoped_session(SessionFactory)
init_db(engine, base=Base, app_config=app.config)

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

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
    except Exception:
        # preserve existing behavior on failure, but log for debugging
        logger.exception("set_response_charset failed")
    return response


def _item_to_dict(item):
    # возвращаем числовую цену, если возможно
    price_value, currency = parse_price_value(item.price_raw)
    return {
        "name": item.name,
        "price": price_value,
        "currency": currency,
        "url": item.url,
        "source_site": item.source_site,
    }


def _reference_item_to_dict(item):
    price_value, currency = parse_price_value(item.price_raw)
    return {
        "name": item.name,
        "price": price_value,
        "currency": currency,
        "url": item.url,
        "source_site": item.source_site,
        "price_raw": item.price_raw,
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
    """Return categories for the reference store from DB (no scraping)."""
    session = db_session()
    ref_store = session.query(Store).filter(Store.is_reference.is_(True)).first()
    # fallback to any store if reference not found
    if ref_store is None:
        stores = list_stores(session)
        ref_store = next((s for s in stores if getattr(s, "is_reference", False)), None)
    if ref_store is None:
        stores = list_stores(session)
        ref_store = stores[0] if stores else None
    store_id_value = cast(int, cast(object, ref_store.id)) if ref_store is not None else None
    categories = list_categories_by_store(session, store_id_value) if store_id_value is not None else []
    product_counts = {}
    if store_id_value is not None:
        try:
            from pricewatch.db.repositories.category_repository import count_products_by_category
            product_counts = count_products_by_category(session, store_id_value)
        except Exception:
            product_counts = {}
    return jsonify({
        'store': _serialize_store(ref_store) if ref_store else None,
        'categories': [dict(_serialize_category(c), product_count=product_counts.get(c.id, 0)) for c in categories],
    })

@app.route('/api/reference-products', methods=['GET'])
def reference_products():
    category = (request.args.get('category') or '').strip()
    if not category:
        return jsonify({'error': 'category query parameter is required'}), 400

    search_query = (request.args.get('q') or '').strip().lower()
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get('page_size', 20))
    except ValueError:
        page_size = 20

    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    reference = registry.reference_adapter()
    builder = ReferenceCatalogBuilder(reference, default_client)
    try:
        catalog = builder.build([category])
    except Exception as exc:
        logger.exception("reference_products failed: %s", exc)
        return jsonify({'error': 'failed to load reference catalog'}), 500

    filtered = []
    for item in catalog:
        if search_query:
            name = (item.name or '').lower()
            source = (item.source_site or '').lower()
            if search_query not in name and search_query not in source:
                continue
        filtered.append(item)

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]
    data = [_reference_item_to_dict(item) for item in page_items]

    return jsonify({
        'items': data,
        'total': total,
        'page': page,
        'per_page': page_size,
        'has_more': end < total,
    })


@app.route('/api/check', methods=['POST'])
def check_missing():
    logger.info("%s", "=" * 50)
    logger.info("📨 Received check request")
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
    logger.info("Main site items: %d (category=%s)", len(main_products), category)

    # ensure MAIN_NORMALIZED is in sync (ReferenceCatalogBuilder usually fills it; tests may monkeypatch)
    MAIN_NORMALIZED.clear()
    for r in main_products:
        MAIN_NORMALIZED.append(normalize_title(r.name))

    # build index: normalize_title -> list of product items
    ref_index = {}
    for r in main_products:
        key = normalize_title(r.name)
        ref_index.setdefault(key, []).append(r)

    missing = []
    scanned = 0
    others = []
    for url in urls:
        if not url.startswith('http'):
            url = 'https://' + url
        logger.info("checking other site: %s", url)
        adapter = registry.for_url(url) or GenericAdapter()
        logger.info("  -> adapter: %s", getattr(adapter, 'name', '<unknown>'))
        site_products = adapter.scrape_url(default_client, url)
        scanned += len(site_products)
        others.extend(site_products)

    # Build a compact summary per-request for legacy API clients/tests.
    # For now compute a lightweight diagnostic using the first reference and first other product.
    def _to_summary(ref_items, other_items):
        if not ref_items:
            return {"status": 2, "status_reason": "no_reference_products", "ref": None}
        ref = ref_items[0]
        ref_price, ref_currency = parse_price_value(ref.price_raw)
        other = other_items[0] if other_items else None
        other_price, other_currency = (parse_price_value(other.price_raw) if other is not None else (None, ""))

        summary: Dict[str, Any] = {"ref": {"price": ref_price, "currency": ref_currency}}
        # invalid reference price
        if ref_price is None:
            summary.update({"status": 2, "status_reason": "invalid_ref_price"})
            return summary
        # currency mismatch
        if ref_currency and other_currency and ref_currency != other_currency:
            summary.update({"status": 2, "status_reason": "currency_mismatch"})
            return summary

        # default compare: if other_price known, compare numeric values
        if other_price is not None:
            summary["status"] = 0 if (ref_price <= other_price) else 1
            return summary

        # fallback: other has no price, treat as missing (status 0)
        summary["status"] = 0
        return summary

    missing.append(_to_summary(main_products, others))

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

    logger.info("Fetching categories for adapter: %s", adapter.name)
    cats = adapter.get_categories(default_client)

    # decode any escaped unicode sequences returned by adapters (e.g. '\u041f...')
    if isinstance(cats, list):
        for c in cats:
            if isinstance(c, dict) and 'name' in c and isinstance(c['name'], str):
                c['name'] = _decode_escapes(c['name'])

    return jsonify({'categories': cats})

def _serialize_store(store):
    return {
        "id": store.id,
        "name": store.name,
        "is_reference": store.is_reference,
        "base_url": store.base_url,
    }


def _serialize_category(cat):
    return {
        "id": cat.id,
        "store_id": cat.store_id,
        "name": cat.name,
        "normalized_name": cat.normalized_name,
        "url": cat.url,
        "external_id": cat.external_id,
        "updated_at": cat.updated_at.isoformat() if cat.updated_at else None,
    }


def _serialize_product(prod):
    return {
        "id": prod.id,
        "store_id": prod.store_id,
        "category_id": prod.category_id,
        "name": prod.name,
        "normalized_name": prod.normalized_name,
        "name_hash": prod.name_hash,
        "price": prod.price,
        "currency": prod.currency,
        "product_url": prod.product_url,
        "source_url": prod.source_url,
        "is_available": prod.is_available,
        "scraped_at": prod.scraped_at.isoformat() if prod.scraped_at else None,
        "updated_at": prod.updated_at.isoformat() if prod.updated_at else None,
    }


def _serialize_mapping(mapping):
    ref_cat = getattr(mapping, "reference_category", None)
    tgt_cat = getattr(mapping, "target_category", None)
    ref_store = getattr(ref_cat, "store", None) if ref_cat else None
    tgt_store = getattr(tgt_cat, "store", None) if tgt_cat else None
    return {
        "id": mapping.id,
        "reference_category_id": getattr(mapping, "reference_category_id", None),
        "target_category_id": getattr(mapping, "target_category_id", None),
        "reference_category_name": getattr(ref_cat, "name", None),
        "target_category_name": getattr(tgt_cat, "name", None),
        "reference_store_id": getattr(ref_store, "id", None) or getattr(ref_cat, "store_id", None),
        "target_store_id": getattr(tgt_store, "id", None) or getattr(tgt_cat, "store_id", None),
        "reference_store_name": getattr(ref_store, "name", None),
        "target_store_name": getattr(tgt_store, "name", None),
        "match_type": getattr(mapping, "match_type", None),
        "confidence": getattr(mapping, "confidence", None),
        "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
    }


def _mapping_list_payload(service, reference_store_id, target_store_id):
    return {
        "mappings": [
            _serialize_mapping(m)
            for m in service.list_category_mappings(reference_store_id=reference_store_id, target_store_id=target_store_id)
        ],
    }


def _serialize_run(run):
    return {
        "id": run.id,
        "store_id": run.store_id,
        "store": _serialize_store(run.store) if getattr(run, "store", None) else None,
        "run_type": run.run_type,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "categories_processed": run.categories_processed,
        "products_processed": run.products_processed,
        "products_created": run.products_created,
        "products_updated": run.products_updated,
        "price_changes_detected": run.price_changes_detected,
        "error_message": run.error_message,
        "metadata_json": run.metadata_json,
    }

@app.route('/service')
def service_page():
    return render_template('service.html', enable_admin_sync=app.config.get('ENABLE_ADMIN_SYNC', True))


@app.route('/api/stores', methods=['GET'])
def api_list_stores():
    session = db_session()
    stores = list_stores(session)
    return jsonify({'stores': [_serialize_store(s) for s in stores]})


@app.route('/api/admin/stores/sync', methods=['POST'])
def api_admin_sync_stores():
    if not app.config.get("ENABLE_ADMIN_SYNC", True):
        return jsonify({'error': 'not found'}), 404
    session = db_session()
    service = StoreService(session)
    try:
        stores = service.sync_with_registry(registry)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("Admin store sync failed: %s", exc)
        return jsonify({'error': str(exc)}), 500
    return jsonify({'stores': [_serialize_store(s) for s in stores]})

@app.route('/api/stores/<int:store_id>/categories', methods=['GET'])
def api_list_store_categories(store_id: int):
    session = db_session()
    cats = list_categories_by_store(session, store_id)
    try:
        from pricewatch.db.repositories.category_repository import count_products_by_category
        product_counts = count_products_by_category(session, store_id)
    except Exception:
        product_counts = {}
    return jsonify({'categories': [dict(_serialize_category(c), product_count=product_counts.get(c.id, 0)) for c in cats]})

@app.route('/api/categories/<int:category_id>/products', methods=['GET'])
def api_list_category_products(category_id: int):
    session = db_session()
    products = list_products_by_category(session, category_id)
    return jsonify({'products': [_serialize_product(p) for p in products]})


@app.route('/api/stores/<int:store_id>/categories/sync', methods=['POST'])
def api_sync_categories(store_id: int):
    session = db_session()
    service = CategorySyncService(session)
    try:
        result = service.sync_store_categories(store_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({'error': str(exc)}), 400
    return jsonify({
        'success': True,
        'store': _serialize_store(result['store']),
        'scrape_run': _serialize_run(result['scrape_run']),
        'categories': [_serialize_category(c) for c in result['categories']],
    })


@app.route('/api/categories/<int:category_id>/products/sync', methods=['POST'])
def api_sync_category_products(category_id: int):
    session = db_session()
    service = ProductSyncService(session)
    try:
        result = service.sync_category_products(category_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({'error': str(exc)}), 400
    return jsonify({
        'success': True,
        'category': _serialize_category(result['category']),
        'store': _serialize_store(result['store']),
        'scrape_run': _serialize_run(result['scrape_run']),
        'summary': result['summary'],
        'products': [_serialize_product(p) for p in result['products']],
    })


@app.route('/api/category-mappings', methods=['GET'])
def api_list_category_mappings():
    session = db_session()
    reference_store_id = request.args.get('reference_store_id', type=int)
    target_store_id = request.args.get('target_store_id', type=int)
    service = MappingService(session)
    return jsonify(_mapping_list_payload(service, reference_store_id, target_store_id))


@app.route('/api/category-mappings', methods=['POST'])
def api_create_category_mapping():
    session = db_session()
    data = request.get_json() or {}
    service = MappingService(session)
    try:
        mapping = service.create_category_mapping(
            reference_category_id=data.get('reference_category_id'),
            target_category_id=data.get('target_category_id'),
            match_type=data.get('match_type'),
            confidence=data.get('confidence'),
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({'error': str(exc)}), 400
    reference_store_id = request.args.get('reference_store_id', type=int)
    target_store_id = request.args.get('target_store_id', type=int)
    payload = dict(_mapping_list_payload(service, reference_store_id, target_store_id))
    payload['mapping'] = _serialize_mapping(mapping)
    return jsonify(payload)


@app.route('/api/category-mappings/<int:mapping_id>', methods=['PUT'])
def api_update_category_mapping(mapping_id: int):
    session = db_session()
    data = request.get_json() or {}
    service = MappingService(session)
    try:
        mapping = service.update_category_mapping(
            mapping_id,
            match_type=data.get('match_type'),
            confidence=data.get('confidence'),
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({'error': str(exc)}), 400
    reference_store_id = request.args.get('reference_store_id', type=int)
    target_store_id = request.args.get('target_store_id', type=int)
    payload = dict(_mapping_list_payload(service, reference_store_id, target_store_id))
    payload['mapping'] = _serialize_mapping(mapping)
    return jsonify(payload)


@app.route('/api/category-mappings/<int:mapping_id>', methods=['DELETE'])
def api_delete_category_mapping(mapping_id: int):
    session = db_session()
    service = MappingService(session)
    try:
        service.delete_category_mapping(mapping_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        return jsonify({'error': str(exc)}), 400
    reference_store_id = request.args.get('reference_store_id', type=int)
    target_store_id = request.args.get('target_store_id', type=int)
    payload = dict(_mapping_list_payload(service, reference_store_id, target_store_id))
    payload.update({'deleted': True, 'mapping_id': mapping_id})
    return jsonify(payload)

@app.route('/api/scrape-runs', methods=['GET'])
def api_list_runs():
    session = db_session()
    store_id = request.args.get('store_id', type=int)
    run_type = request.args.get('run_type')
    status = request.args.get('status')
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', type=int)
    service = ScrapeHistoryService(session)
    runs = service.list_runs(store_id=store_id, run_type=run_type, status=status, limit=limit, offset=offset)
    return jsonify({'runs': [_serialize_run(r) for r in runs]})


@app.route('/api/scrape-runs/<int:run_id>', methods=['GET'])
def api_get_run(run_id: int):
    session = db_session()
    service = ScrapeHistoryService(session)
    try:
        run = service.get_run(run_id)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 404
    return jsonify({'run': _serialize_run(run)})


@app.route('/api/comparison', methods=['POST'])
def api_comparison():
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    payload = request.get_json() or {}
    ref_store_id = payload.get('reference_store_id')
    target_store_id = payload.get('target_store_id')
    ref_category_id = payload.get('reference_category_id')
    target_category_id = payload.get('target_category_id')
    if not (ref_category_id and target_category_id):
        return jsonify({'error': 'reference_category_id and target_category_id are required'}), 400
    session = db_session()
    ref_products = list_products_by_category(session, ref_category_id)
    tgt_products = list_products_by_category(session, target_category_id)
    def _to_item(prod):
        price_str = f"{prod.price or ''} {prod.currency or ''}".strip()
        return {
            'name': prod.name,
            'price_raw': price_str,
            'url': prod.product_url,
            'source_site': prod.store.name if prod.store else '',
        }
    main_products = [_to_item(p) for p in ref_products]
    other_products = [_to_item(p) for p in tgt_products]
    MAIN_NORMALIZED.clear()
    for r in main_products:
        MAIN_NORMALIZED.append(normalize_title(r['name']))
    missing = product_exists_on_main(main_products, other_products)
    return jsonify({
        'missing': missing,
        'total': len(missing),
        'total_urls': len(other_products),
        'scanned': len(other_products),
    })


@app.route('/api/scrape-status', methods=['GET'])
def api_scrape_status():
    session = db_session()
    store_id = request.args.get('store_id', type=int)
    run_type = request.args.get('run_type')
    status = request.args.get('status') or 'running'
    limit = request.args.get('limit', type=int) or 5
    service = ScrapeHistoryService(session)
    runs = service.list_runs(store_id=store_id, run_type=run_type, status=status, limit=limit)
    return jsonify({'runs': [_serialize_run(r) for r in runs]})


def _bootstrap_store_registry():
    session = db_session()
    service = StoreService(session)
    try:
        service.sync_with_registry(registry)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("Failed to bootstrap stores: %s", exc)
    finally:
        db_session.remove()

with app.app_context():
    _bootstrap_store_registry()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
