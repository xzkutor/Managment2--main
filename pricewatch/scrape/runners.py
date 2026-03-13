"""pricewatch.scrape.runners — Runner adapters over existing sync services.

Maps runner_type strings to runner classes that delegate to the domain
sync services (CategorySyncService, ProductSyncService).

Runners are orchestration adapters — they do NOT contain scraping logic.
"""
from __future__ import annotations

import logging
from typing import Any

from pricewatch.scrape.contracts import BaseRunner, RunnerContext, RunnerResult
from pricewatch.scrape.registry import register_runner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session(ctx: RunnerContext) -> Any:
    if ctx.session is None:
        raise RuntimeError("RunnerContext.session must not be None")
    return ctx.session


# ---------------------------------------------------------------------------
# StoreCategorySyncRunner
# ---------------------------------------------------------------------------

@register_runner
class StoreCategorySyncRunner(BaseRunner):
    """Sync categories for a single store.

    Expected params_json keys:
        store_id (int): ID of the store to sync.
    """

    runner_type = "store_category_sync"

    def run(self, ctx: RunnerContext) -> RunnerResult:
        session = _get_session(ctx)
        store_id: int | None = ctx.params.get("store_id")
        if not store_id:
            return RunnerResult(
                status="failed",
                error_message="params.store_id is required for store_category_sync",
            )

        # Import here to avoid circular imports at module load time
        from pricewatch.services.category_sync_service import CategorySyncService  # noqa: PLC0415

        try:
            svc = CategorySyncService(session)
            result = svc.sync_store_categories(store_id)
            categories = result.get("categories", [])
            return RunnerResult(
                status="success",
                categories_processed=len(categories),
                checkpoint_out={
                    "store_id": store_id,
                    "categories_synced": len(categories),
                },
            )
        except Exception as exc:
            logger.exception("StoreCategorySyncRunner failed for store_id=%s: %s", store_id, exc)
            return RunnerResult(status="failed", error_message=str(exc))


# ---------------------------------------------------------------------------
# CategoryProductSyncRunner
# ---------------------------------------------------------------------------

@register_runner
class CategoryProductSyncRunner(BaseRunner):
    """Sync products for a single category.

    Expected params_json keys:
        category_id (int): ID of the category to sync.
    """

    runner_type = "category_product_sync"

    def run(self, ctx: RunnerContext) -> RunnerResult:
        session = _get_session(ctx)
        category_id: int | None = ctx.params.get("category_id")
        if not category_id:
            return RunnerResult(
                status="failed",
                error_message="params.category_id is required for category_product_sync",
            )

        from pricewatch.services.product_sync_service import ProductSyncService  # noqa: PLC0415

        try:
            svc = ProductSyncService(session)
            result = svc.sync_category_products(category_id)
            summary = result.get("summary", {})
            products = result.get("products", [])
            return RunnerResult(
                status="success",
                products_processed=summary.get("total", len(products)),
                products_created=summary.get("created", 0),
                products_updated=summary.get("updated", 0),
                price_changes_detected=summary.get("price_changes", 0),
                checkpoint_out={
                    "category_id": category_id,
                    "summary": summary,
                },
            )
        except Exception as exc:
            logger.exception(
                "CategoryProductSyncRunner failed for category_id=%s: %s", category_id, exc
            )
            return RunnerResult(status="failed", error_message=str(exc))


# ---------------------------------------------------------------------------
# AllStoresCategorySyncRunner
# ---------------------------------------------------------------------------

@register_runner
class AllStoresCategorySyncRunner(BaseRunner):
    """Sync categories for ALL registered stores.

    No required params_json keys.
    """

    runner_type = "all_stores_category_sync"

    def run(self, ctx: RunnerContext) -> RunnerResult:
        session = _get_session(ctx)

        from pricewatch.db.repositories import list_stores  # noqa: PLC0415
        from pricewatch.services.category_sync_service import CategorySyncService  # noqa: PLC0415

        stores = list_stores(session)
        svc = CategorySyncService(session)
        total_cats = 0
        failed_stores: list[int] = []

        for store in stores:
            try:
                result = svc.sync_store_categories(store.id)
                total_cats += len(result.get("categories", []))
            except Exception as exc:
                logger.exception("AllStoresCategorySyncRunner: store %s failed: %s", store.id, exc)
                failed_stores.append(store.id)

        status = "partial" if failed_stores else "success"
        error_message = (
            f"Failed stores: {failed_stores}" if failed_stores else None
        )
        return RunnerResult(
            status=status,
            categories_processed=total_cats,
            error_message=error_message,
            checkpoint_out={
                "stores_total": len(stores),
                "stores_failed": failed_stores,
                "categories_synced": total_cats,
            },
        )

