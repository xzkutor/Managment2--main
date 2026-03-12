# Internal Consumer Inventory — `GET /api/categories` Migration

## Purpose

This document tracks all internal references to `GET /api/categories` (the compatibility endpoint)
as part of the migration to the canonical `GET /api/stores/<store_id>/categories` endpoint.

---

## Summary

| File | Type | Reference | Status |
|---|---|---|---|
| `static/js/index.js` | Frontend runtime | `loadCategories()` calls `/api/stores/${storeId}/categories` | ✅ already canonical |
| `static/js/gap.js` | Frontend runtime | loads ref categories via `/api/stores/${refStore.id}/categories` | ✅ already canonical |
| `static/js/service.js` | Frontend runtime | `/api/categories/<id>/products/sync` (sub-resource, not the list endpoint) | ✅ not affected |
| `static/js/index.js` | Frontend runtime | `/api/categories/<id>/mapped-target-categories` (sub-resource) | ✅ not affected |
| `static/js/gap.js` | Frontend runtime | `/api/categories/<id>/mapped-target-categories` (sub-resource) | ✅ not affected |
| `tests/test_categories_endpoint.py` | Test | `GET /api/categories` — treats compat endpoint as primary | ⚠️ migration target |
| `pricewatch/web/catalog_routes.py` | Backend | defines `GET /api/categories` compat endpoint | ⚠️ define as deprecated after migration |
| `docs/api/openapi_outline.md` | Documentation | listed `GET /api/categories` as primary | ✅ updated to canonical |
| `docs/repository_map.md` | Documentation | listed both endpoints without distinction | ✅ updated to canonical/compatibility |
| `docs/api/db_first.md` | Documentation | missing GET /api/categories section | ✅ updated |

---

## Runtime consumer analysis

### `GET /api/categories` (list endpoint, compat)

**Frontend consumers (runtime):**
- `static/js/index.js` — **already uses canonical** `GET /api/stores/${storeId}/categories` in `loadCategories()`.
  No dependency on `GET /api/categories`.
- `static/js/gap.js` — **already uses canonical** `GET /api/stores/${refStore.id}/categories` in the
  `$targetStoreSelect` change handler.
  No dependency on `GET /api/categories`.

**Test consumers:**
- `tests/test_categories_endpoint.py` — calls `GET /api/categories` directly.
  This is the only test file treating the compat endpoint as primary.
  **Migration action:** rewrite to call canonical endpoint; keep minimal compat coverage.

**No runtime JS/HTML consumers** of `GET /api/categories` (the list form without sub-path) were found.

---

### Sub-path endpoints (not affected by this migration)

The following sub-path endpoints share the `/api/categories/` prefix but are **not** the list endpoint
and are **not** migration targets in this wave:

| Endpoint | Used by |
|---|---|
| `GET /api/categories/<id>/products` | `docs/api/db_first.md` (documented) |
| `GET /api/categories/<id>/mapped-target-categories` | `static/js/index.js`, `static/js/gap.js`, tests |
| `POST /api/categories/<id>/products/sync` | `static/js/service.js`, `pricewatch/web/admin_routes.py` |

---

## Migration status

| Consumer | Migration required | Status |
|---|---|---|
| `static/js/index.js` (category list) | No — already canonical | ✅ done |
| `static/js/gap.js` (ref category list) | No — already canonical | ✅ done |
| `static/js/service.js` (category list) | No — already canonical | ✅ done |
| `tests/test_categories_endpoint.py` | Yes — migrate to canonical endpoint | ✅ done (Commit 5) |
| `pricewatch/web/catalog_routes.py` | Deprecation comment + HTTP headers | ✅ done (Commit 6) |
| `pricewatch/web/serializers.py` | Extract shared `build_store_categories_payload` | ✅ done (Commit 3) |
| `docs/api/db_first.md` | Update wording, add canonical/compat sections | ✅ done (Commit 1) |
| `docs/api/openapi_outline.md` | Move `/api/categories` from Group A to Group C | ✅ done (Commit 1 + 7) |
| `docs/repository_map.md` | Mark canonical/compatibility distinction | ✅ done (Commit 1) |
| `docs/api/categories_migration_inventory.md` | Create inventory document | ✅ done (Commit 2) |

---

## Conclusion

The frontend (JS runtime) **already uses the canonical endpoint** for category list loading.
There are **no active runtime consumers** of `GET /api/categories` list endpoint in this codebase.

All internal consumer migration is complete.

`GET /api/categories` is now:
- formally marked as deprecated via `.. deprecated::` docstring;
- returns HTTP response headers: `Deprecation: true`, `Link`, `Sunset`;
- documented in `docs/api/db_first.md` as a compatibility/migration-target endpoint;
- listed in `docs/api/openapi_outline.md` Group C (legacy/compat);
- covered only by minimal regression tests in `TestCategoriesCompatEndpoint`.

**Next step (future wave):** remove `GET /api/categories` entirely once the Sunset date is determined.

