from __future__ import annotations

from typing import List, Any, Dict

from pricewatch.db.models import Category
from pricewatch.db.repositories import (
    upsert_category,
    list_categories_by_store,
    start_run,
    finish_run,
    fail_run,
    update_counters,
)
from pricewatch.services.utils import resolve_adapter_for_store
from pricewatch.db.models import Store
from pricewatch.core.plugin_base import BaseShopAdapter
from __init__ import default_client

import logging
from pricewatch.services.validation_diagnostics import ensure_metadata, record_validation_error

logger = logging.getLogger(__name__)
VALIDATION_ERRORS_SAMPLE_LIMIT = 10


class CategorySyncService:
    def __init__(self, session):
        self.session = session

    def _get_store(self, store_id: int) -> Store:
        store = self.session.get(Store, store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found")
        return store

    def _adapter_for_store(self, store: Store) -> BaseShopAdapter:
        adapter = resolve_adapter_for_store(store)
        if not adapter:
            raise ValueError(f"Adapter not found for store {store.name}")
        return adapter

    def _ensure_metadata(self, metadata: Dict[str, Any]) -> None:
        # delegate to shared helper
        ensure_metadata(metadata, skipped_key="skipped_invalid_categories", sample_limit=VALIDATION_ERRORS_SAMPLE_LIMIT)

    def _log_skipped_category(
        self,
        reason: str,
        message: str,
        adapter_name: str | None,
        store: Store,
        category_name: str | None = None,
        category_url: str | None = None,
    ) -> None:
        extra = {
            "event": "category_skipped",
            "reason": reason,
            "adapter_name": adapter_name,
            "store_id": getattr(store, "id", None),
            "store_name": getattr(store, "name", None),
            "category_name": category_name,
            "category_url": category_url,
        }
        logger.warning(message, extra=extra)

    def _record_validation_error(
        self,
        metadata: Dict[str, Any],
        reason: str,
        message: str,
        adapter_name: str | None,
        store: Store,
        category_name: str | None = None,
        category_url: str | None = None,
    ) -> None:
        self._ensure_metadata(metadata)
        self._log_skipped_category(
            reason=reason,
            message=message,
            adapter_name=adapter_name,
            store=store,
            category_name=category_name,
            category_url=category_url,
        )
        extra = { }
        if category_name is not None:
            extra["category_name"] = category_name
        if category_url is not None:
            extra["category_url"] = category_url
        if adapter_name is not None:
            extra["adapter_name"] = adapter_name
        if getattr(store, "id", None) is not None:
            extra["store_id"] = getattr(store, "id", None)
        if getattr(store, "name", None):
            extra["store_name"] = store.name

        record_validation_error(
            metadata,
            reason,
            message,
            extra_fields=extra,
            skipped_key="skipped_invalid_categories",
            sample_limit=VALIDATION_ERRORS_SAMPLE_LIMIT,
        )

    def sync_store_categories(self, store_id: int) -> dict[str, Any]:
        store = self._get_store(store_id)
        adapter = self._adapter_for_store(store)
        metadata_json = {
            "store_id": store.id,
            "skipped_invalid_categories": 0,
            "validation_error_counts": {},
            "validation_errors_sample": [],
        }
        run = start_run(self.session, store_id=store.id, run_type="categories", metadata_json=metadata_json)
        metadata = run.metadata_json or {}
        self._ensure_metadata(metadata)

        try:
            raw_categories = adapter.get_categories(default_client) or []
            count = 0
            for cat in raw_categories:
                name = cat.get("name") if isinstance(cat, dict) else getattr(cat, "name", None)
                url = cat.get("url") if isinstance(cat, dict) else getattr(cat, "url", None)
                external_id = cat.get("external_id") if isinstance(cat, dict) else getattr(cat, "external_id", None)
                if not name:
                    # skip invalid category and record metadata
                    self._record_validation_error(
                        metadata,
                        "missing_category_name",
                        "Category skipped because name is missing",
                        getattr(adapter, "name", None),
                        store,
                        category_name=None,
                        category_url=url,
                    )
                    continue
                upsert_category(
                    self.session,
                    store_id=store.id,
                    name=name,
                    external_id=external_id,
                    url=url,
                )
                count += 1
            update_counters(self.session, run.id, categories_processed=count, absolute=True)
            metadata["skipped_invalid_categories"] = metadata.get("skipped_invalid_categories", 0)
            run.metadata_json = metadata
            finish_run(self.session, run.id)
        except Exception as exc:
            fail_run(self.session, run.id, str(exc))
            raise
        categories = list_categories_by_store(self.session, store.id)
        return {"store": store, "scrape_run": run, "categories": categories}

    def get_categories_for_store(self, store_id: int) -> List[Category]:
        return list_categories_by_store(self.session, store_id)

    def sync_reference_store_categories(self) -> dict[str, Any]:
        ref = self.session.query(Store).filter(Store.is_reference.is_(True)).first()
        if not ref:
            raise ValueError("Reference store not found")
        return self.sync_store_categories(ref.id)
