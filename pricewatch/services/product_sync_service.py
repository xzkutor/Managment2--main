from __future__ import annotations

import logging
import re

from typing import Any, Dict, List
from urllib.parse import urljoin

from pricewatch.core.normalize import parse_price_value
from pricewatch.core.plugin_base import BaseShopAdapter
from pricewatch.db.models import Product, Category, Store
from pricewatch.db.repositories import (
    start_run,
    finish_run,
    fail_run,
    update_counters,
    upsert_product,
    list_products_by_category,
)
from pricewatch.services.utils import resolve_adapter_for_store
from pricewatch.db.repositories.category_repository import get_category
from __init__ import default_client
from pricewatch.services.validation_diagnostics import ensure_metadata, record_validation_error

logger = logging.getLogger(__name__)
VALIDATION_ERRORS_SAMPLE_LIMIT = 10


class ProductSyncService:
    def __init__(self, session):
        self.session = session

    def _get_category(self, category_id: int) -> Category:
        category = get_category(self.session, category_id)
        if not category:
            raise ValueError(f"Category {category_id} not found")
        return category

    def _adapter_for_store(self, store: Store) -> BaseShopAdapter:
        adapter = resolve_adapter_for_store(store)
        if not adapter:
            raise ValueError(f"Adapter not found for store {store.name}")
        return adapter

    def _fetch_products(self, adapter: BaseShopAdapter, category: Category):
        category_dto = self._category_to_dto(category)
        if hasattr(adapter, "get_products_by_category"):
            return adapter.get_products_by_category(category_dto, default_client)
        if hasattr(adapter, "scrape_category"):
            target = category.url or category.name
            return adapter.scrape_category(default_client, target)
        raise ValueError("Adapter does not support product scraping")

    def _category_to_dto(self, category: Category) -> Dict[str, Any]:
        return {
            "id": getattr(category, "id", None),
            "external_id": getattr(category, "external_id", None),
            "name": (category.name or ""),
            "url": getattr(category, "url", None),
        }

    def _extract_product_url(self, item: Any) -> Any:
        if isinstance(item, dict):
            return item.get("product_url") or item.get("url")
        return getattr(item, "product_url", None) or getattr(item, "url", None)

    def _normalize_product_url(self, raw_url: Any, category_url: str | None) -> str | None:
        if raw_url is None:
            return None
        if not isinstance(raw_url, str):
            try:
                raw_url = str(raw_url)
            except Exception:
                return None
        trimmed = raw_url.strip()
        if not trimmed:
            return None
        lower = trimmed.lower()
        if category_url and not (lower.startswith("http://") or lower.startswith("https://")):
            try:
                return urljoin(category_url, trimmed)
            except Exception:
                return trimmed
        return trimmed

    # Добавляем централизованную нормализацию product DTO
    def _normalize_product_dto(self, item: Any, category_url: str | None) -> Dict[str, Any]:
        """
        Возвращает нормализованный словарь с ключами:
        name, product_url, price, currency, price_raw, source_url, external_id, description, is_available

        Правила:
        - предпочитать числовое поле `price` (int/float или строку, приводимую к числу);
          если нет — парсить `price_raw` через `parse_price_value`.
        - предпочитать `currency` из DTO, иначе использовать распознанную из `price_raw`.
        - предпочитать `source_url`, затем `source`, затем `source_site` как fallback;
          нормализовать URL через `_normalize_product_url`.
        - поддерживать dict- и object-формат DTO.
        """
        def get_field(name: str):
            if isinstance(item, dict):
                return item.get(name)
            return getattr(item, name, None)

        # basic fields
        name = get_field("name")
        description = get_field("description")
        external_id = get_field("external_id")
        is_available = get_field("is_available")

        # product URL: prefer explicit product/url fields
        raw_product_url = self._extract_product_url(item)
        product_url = self._normalize_product_url(raw_product_url, category_url)

        # source_url: prefer explicit new field then fallbacks
        raw_source = get_field("source_url") or get_field("source") or get_field("source_site")
        source_url = self._normalize_product_url(raw_source, category_url)

        # price and currency resolution
        explicit_price = get_field("price")
        price_raw = get_field("price_raw")
        parsed_price = None
        parsed_currency = None

        # Helper to try convert explicit price to float if possible
        if explicit_price is not None:
            try:
                if isinstance(explicit_price, (int, float)):
                    parsed_price = float(explicit_price)
                elif isinstance(explicit_price, str):
                    # first: try direct numeric conversion (covers "12999")
                    stripped = explicit_price.strip()
                    if stripped:
                        try:
                            parsed_price = float(stripped)
                        except Exception:
                            # direct conversion failed -> try cleaned numeric conversion
                            try:
                                cleaned = stripped.replace('\u00A0', '').replace(' ', '').replace(',', '.')
                                m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
                                if m:
                                    parsed_price = float(m.group(0))
                                    # try to capture currency from the original explicit string
                                    try:
                                        _, maybe_curr = parse_price_value(explicit_price)
                                        if maybe_curr:
                                            parsed_currency = maybe_curr
                                    except Exception:
                                        pass
                                else:
                                    # final fallback: use parse_price_value to also capture currency
                                    parsed_price, parsed_currency = parse_price_value(explicit_price)
                            except Exception:
                                parsed_price, parsed_currency = None, None
                    else:
                        parsed_price = None
                else:
                    # try generic conversion
                    parsed_price = float(explicit_price)
            except Exception:
                # couldn't convert explicit price -> ignore and fallback to price_raw
                parsed_price = None

        # If explicit price (including parsed from explicit string) didn't produce a value,
        # try parse_price_value on price_raw as fallback
        if parsed_price is None:
            try:
                parsed_price_from_raw, parsed_currency_from_raw = parse_price_value(price_raw)
            except Exception:
                parsed_price_from_raw, parsed_currency_from_raw = None, None
            # if we previously obtained a currency from parsing explicit_price, prefer it for now
            if parsed_price_from_raw is not None:
                parsed_price = parsed_price_from_raw
                # only set currency from raw if none set yet
                if not parsed_currency:
                    parsed_currency = parsed_currency_from_raw

        price = parsed_price
        # currency: explicit override takes precedence
        currency = get_field("currency") or parsed_currency

        return {
            "name": name,
            "product_url": product_url,
            "price": price,
            "currency": currency,
            "price_raw": price_raw,
            "source_url": source_url,
            "external_id": external_id,
            "description": description,
            "is_available": is_available,
            "raw_product_url": raw_product_url,
        }

    def sync_category_products(self, category_id: int) -> dict[str, Any]:
        category = self._get_category(category_id)
        store = category.store
        adapter = self._adapter_for_store(store)

        metadata_json = {
            "category_id": category.id,
            "skipped_invalid_products": 0,
            "skipped_missing_url": 0,
            "validation_error_counts": {},
            "validation_errors_sample": [],
        }
        run = start_run(
            self.session,
            store_id=store.id,
            run_type="category_products",
            metadata_json=metadata_json,
        )
        metadata = run.metadata_json or {}
        self._ensure_metadata(metadata)
        skipped_missing_url = metadata.get("skipped_missing_url", 0)
        run.metadata_json = metadata

        try:
            raw_products = self._fetch_products(adapter, category) or []
            processed = created = updated = price_changes = 0
            for item in raw_products:
                processed += 1

                normalized = self._normalize_product_dto(item, category.url)
                name = normalized.get("name")
                if not name:
                    self._record_validation_error(
                        metadata,
                        "missing_product_name",
                        "Product skipped because name is missing",
                        getattr(adapter, "name", None),
                        store,
                        product_name=None,
                    )
                    continue

                product_url = normalized.get("product_url")
                if not product_url:
                    skipped_missing_url += 1
                    metadata["skipped_missing_url"] = skipped_missing_url
                    self._record_validation_error(
                        metadata,
                        "missing_product_url",
                        "Product skipped because product_url is missing",
                        getattr(adapter, "name", None),
                        store,
                        product_name=name,
                        product_url=normalized.get("raw_product_url"),
                        source_url=normalized.get("source_url"),
                    )
                    continue

                description = normalized.get("description")
                external_id = normalized.get("external_id")
                is_available = normalized.get("is_available")
                price = normalized.get("price")
                currency = normalized.get("currency")

                result = upsert_product(
                    self.session,
                    store_id=store.id,
                    product_url=product_url,
                    name=name,
                    price=price,
                    currency=currency,
                    category_id=category.id,
                    external_id=external_id,
                    description=description,
                    source_url=normalized.get("source_url"),
                    is_available=is_available,
                    scrape_run_id=run.id,
                    with_status=True,
                )
                product, was_created, price_changed = result
                if was_created:
                    created += 1
                else:
                    updated += 1
                if price_changed:
                    price_changes += 1
            update_counters(
                self.session,
                run.id,
                products_processed=processed,
                products_created=created,
                products_updated=updated,
                price_changes_detected=price_changes,
                absolute=True,
            )
            metadata["skipped_missing_url"] = skipped_missing_url
            run.metadata_json = metadata
            finish_run(self.session, run.id)
        except Exception as exc:
            fail_run(self.session, run.id, str(exc))
            raise

        products = list_products_by_category(self.session, category.id)
        return {
            "category": category,
            "store": store,
            "scrape_run": run,
            "products": products,
            "summary": {
                "processed": processed,
                "created": created,
                "updated": updated,
                "price_changes": price_changes,
                "skipped_invalid_products": metadata.get("skipped_invalid_products", 0),
                "skipped_missing_url": metadata.get("skipped_missing_url", 0),
                "validation_error_counts": metadata.get("validation_error_counts", {}),
                "validation_errors_sample": metadata.get("validation_errors_sample", []),
            },
        }

    def get_products_for_category(self, category_id: int) -> List[Product]:
        return list_products_by_category(self.session, category_id)

    def _ensure_metadata(self, metadata: Dict[str, Any]) -> None:
        # use shared helper to ensure metadata shape for products
        ensure_metadata(metadata, skipped_key="skipped_invalid_products", sample_limit=VALIDATION_ERRORS_SAMPLE_LIMIT)
        # preserve legacy key used by product sync
        metadata.setdefault("skipped_missing_url", 0)

    def _log_skipped_product(
        self,
        reason: str,
        message: str,
        adapter_name: str | None,
        store: Store,
        category: Category,
        product_name: str | None = None,
        product_url: str | None = None,
        source_url: str | None = None,
    ) -> None:
        extra = {
            "event": "product_skipped",
            "reason": reason,
            "adapter_name": adapter_name,
            "store_id": getattr(store, "id", None),
            "store_name": getattr(store, "name", None),
            "category_id": getattr(category, "id", None),
            "category_name": getattr(category, "name", None),
            "product_name": product_name,
            "product_url": product_url,
            "source_url": source_url,
        }
        logger.warning(message, extra=extra)

    def _record_validation_error(
        self,
        metadata: Dict[str, Any],
        reason: str,
        message: str,
        adapter_name: str | None,
        store: Store,
        category: Category | None = None,
        product_name: str | None = None,
        product_url: str | None = None,
        source_url: str | None = None,
    ) -> None:
        # keep logging behaviour, delegate counters+samples to shared helper
        self._ensure_metadata(metadata)
        self._log_skipped_product(
            reason=reason,
            message=message,
            adapter_name=adapter_name,
            store=store,
            category=category,
            product_name=product_name,
            product_url=product_url,
            source_url=source_url,
        )
        extra = {}
        if product_name is not None:
            extra["product_name"] = product_name
        if product_url is not None:
            extra["product_url"] = product_url
        if source_url is not None:
            extra["source_url"] = source_url
        if adapter_name is not None:
            extra["adapter_name"] = adapter_name
        if category is not None and getattr(category, "id", None) is not None:
            extra["category_id"] = getattr(category, "id", None)
        if category is not None and getattr(category, "name", None):
            extra["category_name"] = category.name

        record_validation_error(
            metadata,
            reason,
            message,
            extra_fields=extra,
            skipped_key="skipped_invalid_products",
            sample_limit=VALIDATION_ERRORS_SAMPLE_LIMIT,
        )
