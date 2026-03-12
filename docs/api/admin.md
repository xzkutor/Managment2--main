# Admin / Service API

## Scope

This document describes operational endpoints used by `/service` and administrative workflows.

These endpoints are part of supported operations, but they are not the same as the primary user-facing comparison contract.

## Store and sync endpoints

### `POST /api/admin/stores/sync`
Synchronize adapter registry metadata into DB stores.

### `POST /api/stores/<store_id>/categories/sync`
Fetch categories for the selected store and persist them.

### `POST /api/categories/<category_id>/products/sync`
Fetch products for the selected category and persist them.

## Category mapping endpoints

### `GET /api/category-mappings`
List category mappings.

### `POST /api/category-mappings`
Create a mapping.

Rules:
- `reference_category_id` must belong to a reference store (`store.is_reference == True`).
- `target_category_id` must not belong to a reference store.
- reference and target categories must not belong to the same store.
- the reference/target pair becomes the identity of the mapping — immutable after creation.

### `PUT /api/category-mappings/<mapping_id>`
Update mapping metadata only (`match_type`, `confidence`).
The category pair is immutable — changing it is not allowed.

### `DELETE /api/category-mappings/<mapping_id>`
Delete a mapping.

### `POST /api/category-mappings/auto-link`

Automatically creates `category_mappings` based on exact `normalized_name` match between reference and target categories.

**Request:**
```json
{
  "reference_store_id": 1,
  "target_store_id": 2
}
```

**Response:**
```json
{
  "created": [
    {
      "reference_category_id": 1,
      "target_category_id": 5,
      "match_type": "exact",
      "confidence": 1.0
    }
  ],
  "skipped_existing": [],
  "summary": {"created": 3, "skipped_existing": 1, "skipped_no_norm": 0}
}
```

Rules:
- Does not create duplicates — existing pairs go into `skipped_existing`.
- Uses `match_type = "exact"`, `confidence = 1.0`.
- `skipped_no_norm` — count of reference categories without a `normalized_name`.
- Fuzzy auto-mapping is **not** in current scope.

## Scrape history endpoints

### `GET /api/scrape-runs`
List scrape run history (with pagination).

### `GET /api/scrape-runs/<run_id>`
Get details for one run.

### `GET /api/scrape-status`
Return current or latest run status, suitable for REST polling from the service UI.

## Contract principles

- admin endpoints may change faster than DB-first read APIs, but should still be documented
- operational side effects must be explicit
- sync endpoints must surface errors clearly
- admin APIs should not be presented as end-user catalog browsing APIs
