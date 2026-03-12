# Adapter Routes Consumer Inventory

## Purpose

This document records all known consumers of the adapter-facing API endpoints:

- `GET /api/adapters`
- `GET /api/adapters/<adapter_name>/categories`

It was created as part of the adapter routes rationalization wave.

---

## Consumer Inventory

### `GET /api/adapters`

| Consumer | Location | Type | Notes |
|---|---|---|---|
| `test_response_charset.py` | `tests/test_response_charset.py:12` | Test-only | Calls `GET /api/adapters` to validate `Content-Type: charset=utf-8` header. Not a runtime product consumer. |
| `test_api_contract.py` | `tests/test_api_contract.py` (implied by `TestAdapterCategories`) | Test-only | Routes are covered by the adapter contract test class. |

**Active runtime frontend consumers:** None found. No `static/js/*.js` file calls `/api/adapters`.

---

### `GET /api/adapters/<adapter_name>/categories`

| Consumer | Location | Type | Notes |
|---|---|---|---|
| `test_app_adapter_categories.py` | `tests/test_app_adapter_categories.py:22` | Test-only | Calls `GET /api/adapters/dummy/categories` with a dummy adapter. |
| `test_adapter_categories_unicode.py` | `tests/test_adapter_categories_unicode.py:19` | Test-only | Calls `GET /api/adapters/escaped/categories` to verify unicode decode. |
| `test_api_contract.py` | `tests/test_api_contract.py:402,416,424` | Test-only | `TestAdapterCategories` covers 200/known, 404/unknown, path segment rules. |

**Active runtime frontend consumers:** None found. No `static/js/*.js` file calls `/api/adapters/<name>/categories`.

---

## Classification Summary

| Consumer bucket | Count | Details |
|---|---|---|
| Active runtime frontend consumers | **0** | Main UI (`index.js`, `gap.js`, `service.js`) does not depend on adapter routes. |
| Python/runtime internal consumers | **0** | No Python code outside `adapter_routes.py` itself calls these endpoints at runtime. |
| Test-only consumers | **4 files** | All remaining consumers are test files. |
| Docs/examples-only consumers | **0** | No code examples call these endpoints. |
| Dead/unused references | **0** | All references are in active test files. |

---

## Conclusion

**The main user-facing UI does not depend on adapter routes.**

Normal catalog, comparison, and gap flows use DB-first endpoints exclusively:
- `GET /api/stores`
- `GET /api/stores/<store_id>/categories`
- `POST /api/comparison`
- `POST /api/gap` / `POST /api/gap/status`

Adapter routes are consumed only by tests.
They exist for internal/admin adapter introspection (live `get_categories()` calls) and are
correctly classified as supported internal/admin-facing endpoints that are not part of the
canonical DB-first catalog API.

**Next steps:**
- No runtime migration required.
- Test coverage should be kept to validate adapter routes remain operational.
- The classification as internal/admin-facing is already reflected in code and docs.

