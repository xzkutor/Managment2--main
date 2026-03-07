from types import SimpleNamespace

import pricewatch.services.category_sync_service as category_sync_service
from pricewatch.services.category_sync_service import CategorySyncService


def test_sync_skips_categories_without_name(monkeypatch):
    store = SimpleNamespace(id=10, name='store')

    # Adapter returns one invalid (no name) and one valid
    class StubAdapter:
        name = 'stub'
        def get_categories(self, client=None):
            return [
                {'name': None, 'url': 'https://example.com/x'},
                {'name': 'Valid Cat', 'url': 'https://example.com/v'},
            ]

    def fake_start_run(session, *, store_id, run_type, metadata_json=None):
        return SimpleNamespace(id=123, store_id=store_id, run_type=run_type, status='running', metadata_json=metadata_json)

    finish_called = []
    def fake_finish_run(session, run_id, **kwargs):
        finish_called.append(run_id)
        return SimpleNamespace(id=run_id, metadata_json={})

    monkeypatch.setattr(category_sync_service, 'start_run', fake_start_run)
    monkeypatch.setattr(category_sync_service, 'finish_run', fake_finish_run)
    monkeypatch.setattr(category_sync_service, 'fail_run', lambda *args, **kwargs: None)
    monkeypatch.setattr(category_sync_service, 'update_counters', lambda *args, **kwargs: None)
    monkeypatch.setattr(category_sync_service, 'upsert_category', lambda *args, **kwargs: None)

    # patch adapter resolver and store lookup
    monkeypatch.setattr(category_sync_service, 'resolve_adapter_for_store', lambda store: StubAdapter())
    monkeypatch.setattr(CategorySyncService, '_get_store', lambda self, store_id: store)
    monkeypatch.setattr(category_sync_service, 'list_categories_by_store', lambda session, store_id: [])

    service = CategorySyncService(session=None)
    result = service.sync_store_categories(store.id)

    # ensure scrape_run metadata captured skipped_invalid_categories
    assert getattr(result['scrape_run'], 'metadata_json') is not None
    md = result['scrape_run'].metadata_json
    assert md.get('skipped_invalid_categories', 0) >= 1
    assert md['validation_error_counts'].get('missing_category_name') >= 1
    # ensure categories list returned is present
    assert 'categories' in result

