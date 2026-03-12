# OpenAPI Outline

## Status

This document is an outline for future OpenAPI formalization. It is intentionally not a complete machine-readable OpenAPI document yet. Its purpose is to define the stable surface that should eventually be exported as OpenAPI for supported endpoints.

## Scope

Included in future OpenAPI:
- supported DB-first endpoints;
- supported admin/service endpoints if maintainers decide they are part of the supported operational API.

Excluded from future OpenAPI by default:
- legacy/debug endpoints;
- experimental parser/testing routes;
- internal-only routes without stability commitment.

## API Grouping

### Group A — DB-First User-Facing API
Representative routes:
- `GET /api/stores`
- `GET /api/stores/<store_id>/categories` (**canonical** categories endpoint)
- `GET /api/categories` (**compatibility only** — migration target, do not add new consumers)
- `POST /api/comparison`
- gap-related read/update endpoints that are part of supported review workflow

Primary characteristics:
- reads from persisted database state;
- stable for UI consumption;
- does not depend on live scrape execution during request handling.

### Group B — Admin / Service API
Representative route families:
- sync categories/products;
- create/update mappings;
- inspect history/runs;
- operational maintenance actions.

Primary characteristics:
- operator-oriented;
- mutating;
- may trigger workflows affecting persisted catalog state.

### Group C — Legacy / Debug API
Representative routes:
- parser playground;
- live scrape check helpers;
- old reference product endpoints;
- `GET /api/categories` (**compatibility/migration target** — implicit reference-store selection; superseded by `GET /api/stores/<store_id>/categories`; scheduled for deprecation after consumer migration).

Primary characteristics:
- unstable or scheduled for deprecation;
- not part of product contract;
- should be excluded from generated public API docs.

## Resource Model Outline

### Store
Fields typically needed in schema:
- `id`
- `name`
- `code` or stable identifier if present
- adapter linkage metadata if exposed
- timestamps if part of contract

### Category
Fields:
- `id`
- `store_id`
- `external_id` and/or source slug
- `name`
- `url` if available
- active/freshness metadata where appropriate

### Product
Fields:
- `id`
- `store_id`
- `category_id`
- `external_id`
- `name`
- `url`
- `price`
- currency / normalized monetary representation
- availability flags if part of stored model
- timestamps / scrape linkage where appropriate

### CategoryMapping
Fields:
- `id`
- `main_store_category_id`
- `other_store_category_id`
- metadata about author/source if tracked

### ProductMapping
Fields:
- `id`
- `main_store_product_id`
- `other_store_product_id`
- confidence or note fields if contractually exposed
- audit metadata if tracked

### ScrapeRun
Fields:
- `id`
- store/category/product scope identifiers
- run status
- started/finished timestamps
- counts/summary stats if exposed

### GapItemStatus
Fields:
- identifying keys for gap context
- explicit status (`in_progress`, `done`)
- actor / timestamp metadata if available

## Response Shape Principles

### List endpoints
Recommended common response shape:
```json
{
  "items": [...],
  "meta": {
    "count": 0
  }
}
```

Alternative existing shapes may be retained short-term, but future formalization should reduce unnecessary inconsistency.

### Mutating endpoints
Recommended response shape:
```json
{
  "status": "ok",
  "data": { ... }
}
```

### Error shape
Recommended baseline:
```json
{
  "error": {
    "code": "validation_error",
    "message": "...",
    "details": { ... }
  }
}
```

## Parameter Outline

### Common query parameters
Potential candidates:
- `store_id`
- `category_id`
- `main_store_id`
- `compare_store_id`
- pagination and limit controls
- filtering by status
- sorting options where required

### Path parameters
Should be reserved for stable resource identity.

### Body payloads
Should define required vs optional fields explicitly for:
- mapping creation;
- mapping update;
- sync trigger requests;
- gap status update requests.

## Status Code Guidance

### Read operations
- `200` for success
- `404` when a requested stable resource does not exist
- `400` for invalid parameter combinations

### Create/update operations
- `200` or `201` for successful mutation depending on semantics
- `409` when uniqueness/invariant conflict occurs
- `422` for semantically invalid payload

### Internal/admin operations
- `202` may be acceptable if workflow becomes asynchronous in the future
- currently synchronous implementations may continue using `200`

## Security / Exposure Notes

Future OpenAPI publication should annotate:
- endpoints intended for browser UI only;
- endpoints intended for authenticated operators;
- endpoints that must never be publicly documented.

## Migration Plan Toward Real OpenAPI

1. Finalize stable supported endpoint inventory.
2. Freeze response envelope conventions.
3. Introduce schema objects for Store/Category/Product/Mapping/Gaps.
4. Exclude legacy/debug routes explicitly.
5. Generate and validate machine-readable OpenAPI spec.
