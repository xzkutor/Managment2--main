"""Tests for /gap page and /api/gap, /api/gap/status endpoints.
Covers all 12 scenarios from business requirements:
  1.  GET /gap renders successfully
  2.  POST /api/gap returns grouped target-only items
  3.  POST /api/gap validates that target categories are mapped
  4.  POST /api/gap reuses comparison-domain target-only definition
  5.  Status defaults to 'new' when no persisted row exists
  6.  POST /api/gap/status creates in_progress
  7.  POST /api/gap/status updates to done
  8.  done items are counted in summary even when filtered from visible list
  9.  search filter works
  10. only_available filter works
  11. status filter works
  12. grouping by target category works
"""
from __future__ import annotations


from pricewatch.db.repositories.store_repository import get_or_create_store
from pricewatch.db.repositories.category_repository import (
    upsert_category,
    create_category_mapping,
)
from pricewatch.db.repositories.product_repository import upsert_product
from pricewatch.db.repositories.mapping_repository import create_product_mapping


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_base(session):
    """Create ref store + target store, one ref category + two target categories."""
    ref_store = get_or_create_store(session, "RefShop", is_reference=True, base_url="https://ref.example.com")
    tgt_store = get_or_create_store(session, "TgtShop", is_reference=False, base_url="https://tgt.example.com")
    ref_cat   = upsert_category(session, store_id=ref_store.id, name="Sticks")
    tgt_cat1  = upsert_category(session, store_id=tgt_store.id, name="Sticks Senior")
    tgt_cat2  = upsert_category(session, store_id=tgt_store.id, name="Sticks Junior")
    session.flush()
    return ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2


def _map_cats(session, ref_cat, tgt_cat1, tgt_cat2):
    create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat1.id, match_type="manual", confidence=1.0)
    create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat2.id, match_type="manual", confidence=1.0)
    session.flush()


def _add_products(session, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2):
    # The ref category is intentionally LEFT EMPTY (no products).
    # With no reference products the heuristic is never invoked and both target
    # products are guaranteed to land in target_only.
    ref_p = None  # no ref product — that is fine for gap testing
    tgt_p1 = upsert_product(session, store_id=tgt_store.id, product_url="https://tgt.example.com/sticks/s1",
                            name="Warrior Covert QR5 Pro Senior", price=9100.0, currency="UAH",
                            category_id=tgt_cat1.id, is_available=True)
    tgt_p2 = upsert_product(session, store_id=tgt_store.id, product_url="https://tgt.example.com/sticks/j1",
                            name="Sher-Wood T90 Lightweight Junior", price=5500.0, currency="UAH",
                            category_id=tgt_cat2.id, is_available=False)
    session.flush()
    return ref_p, tgt_p1, tgt_p2


# ---------------------------------------------------------------------------
# 1. GET /gap renders successfully
# ---------------------------------------------------------------------------

def test_gap_page_renders(client):
    resp = client.get('/gap')
    assert resp.status_code == 200
    # After Commit 8 cutover /gap serves the SPA shell, not the per-page gap.html.
    html = resp.data.decode("utf-8")
    assert 'id="app"' in html, "/gap must serve the SPA shell with #app mount root"
    assert "__PRICEWATCH_BOOTSTRAP__" in html, "/gap must inject the bootstrap payload"


# ---------------------------------------------------------------------------
# 2. POST /api/gap returns grouped target-only items
# ---------------------------------------------------------------------------

def test_api_gap_returns_groups(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        ref_p, tgt_p1, tgt_p2 = _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2)
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat1_id = tgt_cat1.id
        tgt_cat2_id = tgt_cat2.id

    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat1_id, tgt_cat2_id],
        'statuses': ['new', 'in_progress', 'done'],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'groups' in data
    assert 'summary' in data
    # Both target products are target-only (no confirmed match)
    assert data['summary']['total'] == 2


# ---------------------------------------------------------------------------
# 3. POST /api/gap validates that target categories are mapped
# ---------------------------------------------------------------------------

def test_api_gap_rejects_unmapped_category(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        # Only map tgt_cat1, NOT tgt_cat2
        create_category_mapping(session=s, reference_category_id=ref_cat.id,
                                target_category_id=tgt_cat1.id, match_type="manual")
        s.flush()
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat2_id = tgt_cat2.id  # NOT mapped

    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat2_id],
        'statuses': ['new'],
    })
    assert resp.status_code == 400
    assert 'error' in resp.get_json()


# ---------------------------------------------------------------------------
# 4. POST /api/gap reuses comparison-domain target-only definition
#    (confirmed mapped products do NOT appear in gap)
# ---------------------------------------------------------------------------

def test_api_gap_excludes_confirmed_matches(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        # Create a ref product explicitly so we can build a confirmed mapping
        ref_p = upsert_product(s, store_id=ref_store.id,
                               product_url="https://ref.example.com/sticks/ref-confirm",
                               name="Reebok 18K Pump Senior", price=7000.0, currency="UAH",
                               category_id=ref_cat.id, is_available=True)
        tgt_p1 = upsert_product(s, store_id=tgt_store.id, product_url="https://tgt.example.com/sticks/s1",
                                name="Warrior Covert QR5 Pro Senior", price=9100.0, currency="UAH",
                                category_id=tgt_cat1.id, is_available=True)
        tgt_p2 = upsert_product(s, store_id=tgt_store.id, product_url="https://tgt.example.com/sticks/j1",
                                name="Sher-Wood T90 Lightweight Junior", price=5500.0, currency="UAH",
                                category_id=tgt_cat2.id, is_available=False)
        s.flush()
        # Confirm a product mapping: tgt_p1 matched to ref_p (forced, bypasses heuristic)
        create_product_mapping(s, reference_product_id=ref_p.id, target_product_id=tgt_p1.id,
                               match_status='confirmed', confidence=1.0)
        s.flush()
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat1_id = tgt_cat1.id
        tgt_cat2_id = tgt_cat2.id
        tgt_p1_id = tgt_p1.id

    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat1_id, tgt_cat2_id],
        'statuses': ['new', 'in_progress', 'done'],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    # tgt_p1 is confirmed — must NOT appear in gap
    all_prod_ids = [
        item['target_product']['id']
        for g in data['groups']
        for item in g['items']
    ]
    assert tgt_p1_id not in all_prod_ids
    # tgt_p2 is still target-only
    assert data['summary']['total'] == 1


# ---------------------------------------------------------------------------
# 5. Status defaults to 'new' when no persisted row exists
# ---------------------------------------------------------------------------

def test_gap_status_default_new(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        ref_p, tgt_p1, tgt_p2 = _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2)
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat1_id = tgt_cat1.id
        tgt_p1_id = tgt_p1.id

    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat1_id],
        'statuses': ['new', 'in_progress', 'done'],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    items = [item for g in data['groups'] for item in g['items']]
    tgt_p1_item = next((i for i in items if i['target_product']['id'] == tgt_p1_id), None)
    assert tgt_p1_item is not None
    assert tgt_p1_item['status'] == 'new'


# ---------------------------------------------------------------------------
# 6. POST /api/gap/status creates in_progress
# ---------------------------------------------------------------------------

def test_gap_status_create_in_progress(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, _ = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, _)
        ref_p, tgt_p1, _ = _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, _)
        ref_cat_id = ref_cat.id
        tgt_p1_id = tgt_p1.id

    resp = client.post('/api/gap/status', json={
        'reference_category_id': ref_cat_id,
        'target_product_id': tgt_p1_id,
        'status': 'in_progress',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['item']['status'] == 'in_progress'


# ---------------------------------------------------------------------------
# 7. POST /api/gap/status updates to done
# ---------------------------------------------------------------------------

def test_gap_status_update_to_done(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        ref_p, tgt_p1, _ = _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2)
        ref_cat_id = ref_cat.id
        tgt_p1_id = tgt_p1.id

    # First set in_progress
    client.post('/api/gap/status', json={
        'reference_category_id': ref_cat_id,
        'target_product_id': tgt_p1_id,
        'status': 'in_progress',
    })
    # Then update to done
    resp = client.post('/api/gap/status', json={
        'reference_category_id': ref_cat_id,
        'target_product_id': tgt_p1_id,
        'status': 'done',
    })
    assert resp.status_code == 200
    assert resp.get_json()['item']['status'] == 'done'


# ---------------------------------------------------------------------------
# 8. done items counted in summary even when filtered from visible list
# ---------------------------------------------------------------------------

def test_done_items_counted_in_summary(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        ref_p, tgt_p1, tgt_p2 = _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2)
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat1_id = tgt_cat1.id
        tgt_cat2_id = tgt_cat2.id
        tgt_p1_id = tgt_p1.id

    # Mark tgt_p1 as done
    client.post('/api/gap/status', json={
        'reference_category_id': ref_cat_id,
        'target_product_id': tgt_p1_id,
        'status': 'done',
    })

    # Load gap with default visible statuses (new + in_progress) — done hidden
    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat1_id, tgt_cat2_id],
        'statuses': ['new', 'in_progress'],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    # summary.total includes done
    assert data['summary']['total'] == 2
    assert data['summary']['done'] == 1
    # visible groups don't include done item
    visible_ids = [
        item['target_product']['id']
        for g in data['groups']
        for item in g['items']
    ]
    assert tgt_p1_id not in visible_ids


# ---------------------------------------------------------------------------
# 9. Search filter works
# ---------------------------------------------------------------------------

def test_search_filter(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2)
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat1_id = tgt_cat1.id
        tgt_cat2_id = tgt_cat2.id

    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat1_id, tgt_cat2_id],
        'search': 'Sher-Wood',
        'statuses': ['new', 'in_progress', 'done'],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    items = [item for g in data['groups'] for item in g['items']]
    # Only Sher-Wood product should be visible
    assert len(items) == 1
    assert 'Sher-Wood' in items[0]['target_product']['name']


# ---------------------------------------------------------------------------
# 10. only_available filter works
# ---------------------------------------------------------------------------

def test_only_available_filter(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        ref_p, tgt_p1, tgt_p2 = _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2)
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat1_id = tgt_cat1.id
        tgt_cat2_id = tgt_cat2.id
        tgt_p1_id = tgt_p1.id  # is_available=True
        tgt_p2_id = tgt_p2.id  # is_available=False

    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat1_id, tgt_cat2_id],
        'only_available': True,
        'statuses': ['new', 'in_progress', 'done'],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    items = [item for g in data['groups'] for item in g['items']]
    ids = [i['target_product']['id'] for i in items]
    assert tgt_p1_id in ids
    assert tgt_p2_id not in ids


# ---------------------------------------------------------------------------
# 11. Status filter works
# ---------------------------------------------------------------------------

def test_status_filter(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        ref_p, tgt_p1, tgt_p2 = _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2)
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat1_id = tgt_cat1.id
        tgt_cat2_id = tgt_cat2.id
        tgt_p1_id = tgt_p1.id

    # Mark tgt_p1 as in_progress
    client.post('/api/gap/status', json={
        'reference_category_id': ref_cat_id,
        'target_product_id': tgt_p1_id,
        'status': 'in_progress',
    })

    # Request only 'in_progress' items
    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat1_id, tgt_cat2_id],
        'statuses': ['in_progress'],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    items = [item for g in data['groups'] for item in g['items']]
    assert len(items) == 1
    assert items[0]['target_product']['id'] == tgt_p1_id
    assert items[0]['status'] == 'in_progress'


# ---------------------------------------------------------------------------
# 12. Grouping by target category works
# ---------------------------------------------------------------------------

def test_grouping_by_target_category(client, db_session_scope):
    with db_session_scope() as s:
        ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2 = _make_base(s)
        _map_cats(s, ref_cat, tgt_cat1, tgt_cat2)
        _add_products(s, ref_store, tgt_store, ref_cat, tgt_cat1, tgt_cat2)
        ref_cat_id = ref_cat.id
        tgt_store_id = tgt_store.id
        tgt_cat1_id = tgt_cat1.id
        tgt_cat2_id = tgt_cat2.id
        tgt_cat1_name = tgt_cat1.name
        tgt_cat2_name = tgt_cat2.name

    resp = client.post('/api/gap', json={
        'target_store_id': tgt_store_id,
        'reference_category_id': ref_cat_id,
        'target_category_ids': [tgt_cat1_id, tgt_cat2_id],
        'statuses': ['new', 'in_progress', 'done'],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    groups = data['groups']
    group_names = [g['target_category']['name'] for g in groups]
    assert tgt_cat1_name in group_names
    assert tgt_cat2_name in group_names
    # Each group has exactly one item from our test data
    for g in groups:
        assert g['count'] == 1
        assert len(g['items']) == 1

