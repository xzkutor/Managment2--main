from flask import Flask, render_template, request, jsonify, current_app
from flask_cors import CORS
from bs4 import BeautifulSoup
from typing import Any, Dict, cast

import logging

from pricewatch.core.registry import get_registry
from pricewatch.core.reference_service import ReferenceCatalogBuilder
from pricewatch.core.generic_adapter import GenericAdapter
from pricewatch.core.normalize import (
    parse_price_value,
    normalize_title,
    MAIN_NORMALIZED,
)
from pricewatch.net.http_client import default_client
from pricewatch.db import Base, init_engine, init_db, get_session_factory, get_scoped_session
from pricewatch.db.repositories import (
    list_stores,
    list_categories_by_store,
    list_products_by_category,
    create_product_mapping,
)
from pricewatch.services.category_sync_service import CategorySyncService
from pricewatch.services.product_sync_service import ProductSyncService
from pricewatch.services.mapping_service import MappingService
from pricewatch.services.scrape_history_service import ScrapeHistoryService
from pricewatch.services.store_service import StoreService
from pricewatch.services.comparison_service import ComparisonService
from pricewatch.services.category_matching_service import CategoryMatchingService
from pricewatch.db.repositories.category_repository import list_mapped_target_categories
from pricewatch.db.models import Store, ProductMapping
from pricewatch.services.gap_service import GapService
# Boundary-validation schemas (Pydantic DTOs — only at HTTP boundary)
from pricewatch.schemas.validation import parse_request_body
from pricewatch.schemas.requests.comparison import ComparisonRequest, ConfirmMatchRequest
from pricewatch.schemas.requests.gap import GapRequest, GapStatusRequest
from pricewatch.schemas.requests.mappings import (
    AutoLinkCategoryMappingsRequest,
    CreateCategoryMappingRequest,
    UpdateCategoryMappingRequest,
)

logger = logging.getLogger(__name__)


def _get_db_session():
    """Return the scoped-session bound to the current Flask app context."""
    return current_app.extensions["db_scoped_session"]


def create_app(config_override=None):
    """Application factory.

    Parameters
    ----------
    config_override:
        Optional dict of Flask/app config values applied *before* DB
        initialisation.  Pass ``{"DATABASE_URL": "sqlite:///:memory:",
        "TESTING": True}`` to point the app at a test database.

    Returns
    -------
    Flask
        A fully configured Flask application instance with its own DB wiring.
    """
    flask_app = Flask(__name__)
    CORS(flask_app)
    flask_app.config.setdefault("ENABLE_ADMIN_SYNC", True)
    flask_app.json.ensure_ascii = False

    if config_override:
        flask_app.config.update(config_override)

    # --- DB wiring (per-app instance, not global) ---
    _engine = init_engine(flask_app.config)
    _factory = get_session_factory(_engine)
    _scoped = get_scoped_session(_factory)
    init_db(_engine, base=Base, app_config=flask_app.config)

    flask_app.extensions["db_engine"] = _engine
    flask_app.extensions["db_session_factory"] = _factory
    flask_app.extensions["db_scoped_session"] = _scoped

    @flask_app.teardown_appcontext
    def shutdown_session(exception=None):  # noqa: F811
        flask_app.extensions["db_scoped_session"].remove()

    # Bootstrap store registry only in non-test mode
    if not flask_app.config.get("TESTING"):
        _reg = get_registry()
        with flask_app.app_context():
            _sess = _scoped()
            _svc = StoreService(_sess)
            try:
                _svc.sync_with_registry(_reg)
                _sess.commit()
            except Exception as exc:  # pragma: no cover
                _sess.rollback()
                logger.exception("Failed to bootstrap stores: %s", exc)
            finally:
                _scoped.remove()

    _register_routes(flask_app)
    return flask_app



# ---------------------------------------------------------------------------
# Pure serialization helpers (no DB session needed)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Serialization helpers (pure, no DB session)
# ---------------------------------------------------------------------------

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


def _mapping_list_payload(service, reference_store_id, target_store_id) -> Dict[str, Any]:
    return {
        "mappings": [
            _serialize_mapping(m)
            for m in service.list_category_mappings(
                reference_store_id=reference_store_id,
                target_store_id=target_store_id,
            )
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


def _serialize_product_mapping(pm: ProductMapping) -> dict:
    ref = getattr(pm, "reference_product", None)
    tgt = getattr(pm, "target_product", None)
    return {
        "id": pm.id,
        "reference_product_id": pm.reference_product_id,
        "target_product_id": pm.target_product_id,
        "reference_product": _serialize_product(ref) if ref else None,
        "target_product": _serialize_product(tgt) if tgt else None,
        "match_status": pm.match_status,
        "confidence": pm.confidence,
        "comment": pm.comment,
        "updated_at": pm.updated_at.isoformat() if pm.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Route registration (called by create_app)
# ---------------------------------------------------------------------------

def _register_routes(flask_app):  # noqa: C901  (complexity OK for route hub)
    _reg = get_registry()

    @flask_app.after_request
    def set_response_charset(response):
        """Ensure responses include charset=utf-8 in Content-Type."""
        try:
            content_type = response.headers.get('Content-Type', '')
            if 'charset' not in content_type.lower():
                mimetype = response.mimetype or ''
                if mimetype in ('application/json', 'text/html', 'application/javascript'):
                    response.headers['Content-Type'] = f"{mimetype}; charset=utf-8"
        except Exception:
            logger.exception("set_response_charset failed")
        return response

    @flask_app.route('/')
    def index():
        return render_template('index.html')

    @flask_app.route('/service')
    def service_page():
        return render_template('service.html', enable_admin_sync=current_app.config.get('ENABLE_ADMIN_SYNC', True))

    @flask_app.route('/gap')
    def gap_page():
        return render_template('gap.html')

    @flask_app.route('/api/adapters', methods=['GET'])
    def adapters_list():
        """Return the list of available adapters and their supported domains."""
        adapters = []
        for adapter in _reg.adapters:
            if getattr(adapter, 'is_reference', False):
                continue
            adapters.append({'name': adapter.name, 'domains': adapter.domains})
        return jsonify({'adapters': adapters})

    @flask_app.route('/api/categories', methods=['GET'])
    def categories_list():
        """Return categories for the reference store from DB (no scraping)."""
        session = _get_db_session()()
        ref_store = session.query(Store).filter(Store.is_reference.is_(True)).first()
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

    @flask_app.route('/api/adapters/<adapter_name>/categories', methods=['GET'])
    def adapter_categories(adapter_name):
        """Return categories produced by the named adapter (by adapter.name)."""
        adapter = None
        for a in _reg.adapters:
            if a.name == adapter_name:
                adapter = a
                break
        if not adapter:
            return jsonify({'error': 'adapter not found'}), 404
        logger.info("Fetching categories for adapter: %s", adapter.name)
        cats = adapter.get_categories(default_client)
        if isinstance(cats, list):
            for c in cats:
                if isinstance(c, dict) and 'name' in c and isinstance(c['name'], str):
                    c['name'] = _decode_escapes(c['name'])
        return jsonify({'categories': cats})

    @flask_app.route('/api/stores', methods=['GET'])
    def api_list_stores():
        session = _get_db_session()()
        stores = list_stores(session)
        return jsonify({'stores': [_serialize_store(s) for s in stores]})

    @flask_app.route('/api/admin/stores/sync', methods=['POST'])
    def api_admin_sync_stores():
        if not current_app.config.get("ENABLE_ADMIN_SYNC", True):
            return jsonify({'error': 'not found'}), 404
        session = _get_db_session()()
        service = StoreService(session)
        try:
            stores = service.sync_with_registry(_reg)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("Admin store sync failed: %s", exc)
            return jsonify({'error': str(exc)}), 500
        return jsonify({'stores': [_serialize_store(s) for s in stores]})

    @flask_app.route('/api/stores/<int:store_id>/categories', methods=['GET'])
    def api_list_store_categories(store_id: int):
        session = _get_db_session()()
        cats = list_categories_by_store(session, store_id)
        try:
            from pricewatch.db.repositories.category_repository import count_products_by_category
            product_counts = count_products_by_category(session, store_id)
        except Exception:
            product_counts = {}
        return jsonify({'categories': [dict(_serialize_category(c), product_count=product_counts.get(c.id, 0)) for c in cats]})

    @flask_app.route('/api/categories/<int:category_id>/products', methods=['GET'])
    def api_list_category_products(category_id: int):
        session = _get_db_session()()
        products = list_products_by_category(session, category_id)
        return jsonify({'products': [_serialize_product(p) for p in products]})

    @flask_app.route('/api/categories/<int:reference_category_id>/mapped-target-categories', methods=['GET'])
    def api_mapped_target_categories(reference_category_id: int):
        """Return all target categories mapped to the given reference category.

        Optional query param: ``?target_store_id=<id>`` to filter by target store.
        """
        session = _get_db_session()()
        target_store_id = request.args.get('target_store_id', type=int)
        from pricewatch.db.models import Category as _Category
        ref_cat = session.get(_Category, reference_category_id)
        mappings = list_mapped_target_categories(
            session, reference_category_id, target_store_id=target_store_id
        )
        result = []
        target_store_meta = None
        for m in mappings:
            tgt = getattr(m, "target_category", None)
            if tgt is None:
                continue
            tgt_store = getattr(tgt, "store", None)
            if target_store_meta is None and tgt_store is not None:
                target_store_meta = _serialize_store(tgt_store)
            result.append({
                "target_category_id": tgt.id,
                "target_category_name": tgt.name,
                "target_store_id": tgt.store_id,
                "target_store_name": getattr(tgt_store, "name", None),
                "match_type": m.match_type,
                "confidence": m.confidence,
                "mapping_id": m.id,
            })
        return jsonify({
            "reference_category": _serialize_category(ref_cat) if ref_cat else {"id": reference_category_id},
            "target_store": target_store_meta,
            "mapped_target_categories": result,
        })

    @flask_app.route('/api/stores/<int:store_id>/categories/sync', methods=['POST'])
    def api_sync_categories(store_id: int):
        session = _get_db_session()()
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

    @flask_app.route('/api/categories/<int:category_id>/products/sync', methods=['POST'])
    def api_sync_category_products(category_id: int):
        session = _get_db_session()()
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

    @flask_app.route('/api/category-mappings/auto-link', methods=['POST'])
    def api_auto_link_category_mappings():
        """Auto-create category mappings by exact normalized_name match."""
        payload, err = parse_request_body(AutoLinkCategoryMappingsRequest)
        if err:
            return err
        session = _get_db_session()()
        try:
            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=payload.reference_store_id,
                target_store_id=payload.target_store_id,
            )
            session.commit()
        except ValueError as exc:
            session.rollback()
            return jsonify({'error': str(exc)}), 400
        except Exception as exc:
            session.rollback()
            logger.exception("auto_link_category_mappings failed: %s", exc)
            return jsonify({'error': 'Internal server error'}), 500
        return jsonify(result)

    @flask_app.route('/api/category-mappings', methods=['GET'])
    def api_list_category_mappings():
        session = _get_db_session()()
        reference_store_id = request.args.get('reference_store_id', type=int)
        target_store_id = request.args.get('target_store_id', type=int)
        service = MappingService(session)
        return jsonify(_mapping_list_payload(service, reference_store_id, target_store_id))

    @flask_app.route('/api/category-mappings', methods=['POST'])
    def api_create_category_mapping():
        payload, err = parse_request_body(CreateCategoryMappingRequest)
        if err:
            return err
        session = _get_db_session()()
        service = MappingService(session)
        try:
            mapping = service.create_category_mapping(
                reference_category_id=payload.reference_category_id,
                target_category_id=payload.target_category_id,
                match_type=payload.match_type,
                confidence=payload.confidence,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            return jsonify({'error': str(exc)}), 400
        reference_store_id = request.args.get('reference_store_id', type=int)
        target_store_id = request.args.get('target_store_id', type=int)
        response_payload = dict(_mapping_list_payload(service, reference_store_id, target_store_id))
        response_payload['mapping'] = _serialize_mapping(mapping)
        return jsonify(response_payload)

    @flask_app.route('/api/category-mappings/<int:mapping_id>', methods=['PUT'])
    def api_update_category_mapping(mapping_id: int):
        payload, err = parse_request_body(UpdateCategoryMappingRequest)
        if err:
            return err
        session = _get_db_session()()
        service = MappingService(session)
        try:
            mapping = service.update_category_mapping(
                mapping_id,
                match_type=payload.match_type,
                confidence=payload.confidence,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            return jsonify({'error': str(exc)}), 400
        reference_store_id = request.args.get('reference_store_id', type=int)
        target_store_id = request.args.get('target_store_id', type=int)
        response_payload = dict(_mapping_list_payload(service, reference_store_id, target_store_id))
        response_payload['mapping'] = _serialize_mapping(mapping)
        return jsonify(response_payload)

    @flask_app.route('/api/category-mappings/<int:mapping_id>', methods=['DELETE'])
    def api_delete_category_mapping(mapping_id: int):
        session = _get_db_session()()
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

    @flask_app.route('/api/scrape-runs', methods=['GET'])
    def api_list_runs():
        session = _get_db_session()()
        store_id = request.args.get('store_id', type=int)
        run_type = request.args.get('run_type')
        status = request.args.get('status')
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int)
        service = ScrapeHistoryService(session)
        runs = service.list_runs(store_id=store_id, run_type=run_type, status=status,
                                  limit=limit, offset=offset)
        return jsonify({'runs': [_serialize_run(r) for r in runs]})

    @flask_app.route('/api/scrape-runs/<int:run_id>', methods=['GET'])
    def api_get_run(run_id: int):
        session = _get_db_session()()
        service = ScrapeHistoryService(session)
        try:
            run = service.get_run(run_id)
        except Exception as exc:
            return jsonify({'error': str(exc)}), 404
        return jsonify({'run': _serialize_run(run)})

    @flask_app.route('/api/comparison/confirm-match', methods=['POST'])
    def api_comparison_confirm_match():
        """Persist a confirmed product match into product_mappings."""
        payload, err = parse_request_body(ConfirmMatchRequest)
        if err:
            return err
        session = _get_db_session()()
        try:
            pm = create_product_mapping(
                session,
                reference_product_id=payload.reference_product_id,
                target_product_id=payload.target_product_id,
                match_status=payload.match_status or 'confirmed',
                confidence=payload.confidence,
                comment=payload.comment,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("confirm-match failed: %s", exc)
            return jsonify({'error': str(exc)}), 400
        return jsonify({'product_mapping': _serialize_product_mapping(pm)})

    @flask_app.route('/api/comparison', methods=['POST'])
    def api_comparison():
        """Compare products from a reference category against mapped target categories."""
        payload, err = parse_request_body(ComparisonRequest)
        if err:
            return err
        session = _get_db_session()()
        try:
            svc_kwargs: dict = {"reference_category_id": payload.reference_category_id}
            if payload.target_category_ids is not None:
                svc_kwargs["target_category_ids"] = payload.target_category_ids
            elif payload.target_category_id is not None:
                svc_kwargs["target_category_id"] = payload.target_category_id
            if payload.target_store_id is not None:
                svc_kwargs["target_store_id"] = payload.target_store_id
            result = ComparisonService(session).compare(**svc_kwargs)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception as exc:
            logger.exception("api_comparison failed: %s", exc)
            return jsonify({'error': 'Internal server error'}), 500
        return jsonify(result)

    @flask_app.route('/api/gap', methods=['POST'])
    def api_gap():
        """Return grouped target-only (gap) items for a reference category + target categories."""
        payload, err = parse_request_body(GapRequest)
        if err:
            return err
        session = _get_db_session()()
        try:
            result = GapService(session).build_gap_view(
                target_store_id=payload.target_store_id,
                reference_category_id=payload.reference_category_id,
                target_category_ids=payload.target_category_ids,
                search=payload.search,
                only_available=payload.only_available,
                statuses=payload.statuses,
            )
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception as exc:
            logger.exception("api_gap failed: %s", exc)
            return jsonify({'error': 'Internal server error'}), 500
        return jsonify(result)

    @flask_app.route('/api/gap/status', methods=['POST'])
    def api_gap_status():
        """Persist a gap item review status (in_progress or done)."""
        payload, err = parse_request_body(GapStatusRequest)
        if err:
            return err
        session = _get_db_session()()
        try:
            result = GapService(session).set_gap_item_status(
                reference_category_id=payload.reference_category_id,
                target_product_id=payload.target_product_id,
                status=payload.status,
            )
            session.commit()
        except ValueError as exc:
            session.rollback()
            return jsonify({'error': str(exc)}), 400
        except Exception as exc:
            session.rollback()
            logger.exception("api_gap_status failed: %s", exc)
            return jsonify({'error': 'Internal server error'}), 500
        return jsonify({'success': True, 'item': result})

    @flask_app.route('/api/scrape-status', methods=['GET'])
    def api_scrape_status():
        session = _get_db_session()()
        store_id = request.args.get('store_id', type=int)
        run_type = request.args.get('run_type')
        status = request.args.get('status') or 'running'
        limit = request.args.get('limit', type=int) or 5
        service = ScrapeHistoryService(session)
        runs = service.list_runs(store_id=store_id, run_type=run_type, status=status, limit=limit)
        return jsonify({'runs': [_serialize_run(r) for r in runs]})


# ---------------------------------------------------------------------------
# Module-level singletons for backward-compatible runtime startup
# ---------------------------------------------------------------------------

app = create_app()
registry = get_registry()

# Backward-compat aliases so ``import app; app.db_session()`` still works
db_session = app.extensions["db_scoped_session"]
engine = app.extensions["db_engine"]
SessionFactory = app.extensions["db_session_factory"]


if __name__ == '__main__':
    app.run(debug=True, port=5000)

