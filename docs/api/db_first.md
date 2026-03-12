# DB-first API Specification

## Purpose

This document defines the supported read/query API for the main user-facing workflow.

The central rule is:

> Main comparison and browsing flows operate on persisted database state, not on live scraping.

Administrative synchronization endpoints are specified separately in `docs/api/admin.md`.

## Supported endpoint family

The following endpoints belong to the primary DB-first flow:

- `GET /api/stores`
- `GET /api/stores/<store_id>/categories`
- `GET /api/categories/<category_id>/products`
- `GET /api/categories/<category_id>/mapped-target-categories`
- `POST /api/comparison`
- `POST /api/comparison/confirm-match`
- `POST /api/gap`
- `POST /api/gap/status`

## Common API rules

### Read source

Unless explicitly documented otherwise, these endpoints read from the database.

### Error model

Validation errors must return `400`.
Missing resources should return a resource-appropriate `404` if the implementation distinguishes them.
Unexpected failures should return `5xx` and must not be disguised as empty results.

### Stability level

These endpoints are considered supported for UI consumption.
They must be documented and tested more strictly than legacy/debug endpoints.

## `GET /api/stores`

Returns the list of stores persisted in the database.

### Semantics

- read-only;
- should not trigger registry sync;
- result order should be deterministic if the implementation supports it.

### Response shape

At minimum, each item should identify the store sufficiently for UI selection.

## `GET /api/stores/<store_id>/categories`

Returns categories for a selected store from the database.

### Semantics

- read-only;
- no live scraping;
- categories are store-local objects.

### Validation

- invalid `store_id` format or unsupported id should return an error consistent with the project’s API style.

## `GET /api/categories/<category_id>/products`

Returns products for a category from the database.

### Semantics

- read-only;
- product list is derived from synchronized persisted rows;
- no runtime comparison is implied by this endpoint.

## `GET /api/categories/<category_id>/mapped-target-categories`

Returns mapped target categories for the selected reference category.

### Query parameters

- `target_store_id` — optional filter that limits results to one target store.

### Semantics

- valid only in reference-category context;
- response should include enough information for UI checkbox selection;
- if no mappings exist, the system should return an empty result or a response style already established by implementation, but the absence of mappings must be distinguishable from request failure.

## `POST /api/comparison`

Performs comparison using persisted products and existing mapping state.

## Request contract

The request must identify:

- the reference category;
- the target scope through one or more mapped target categories;
- any optional filtering/scoping fields supported by the implementation.

### Required invariants

- comparison is allowed only for explicitly mapped categories;
- target categories outside the mapped set are invalid;
- comparison must not trigger live scraping.

## Result model

The comparison result is conceptually divided into:

- confirmed matches;
- candidate groups;
- reference-only products;
- target-only products.

### Semantic rules

- confirmed product mappings are authoritative;
- candidate groups are runtime-only and advisory;
- target-only products are those not covered by confirmed mappings or candidate groups;
- reference-only products are those without acceptable target counterpart.

## `POST /api/comparison/confirm-match`

Confirms a product mapping.

### Purpose

Promote a runtime or manually chosen relation into a persisted `ProductMapping`.

### Semantics

- this is a state-changing endpoint;
- confirmation must persist authoritative mapping state;
- confirmation should reduce future ambiguity in comparison results.

### Validation

The endpoint should reject:

- missing reference or target identifiers;
- logically invalid pairs;
- duplicate confirmation requests, unless idempotency is intentionally implemented.

## `POST /api/gap`

Returns grouped target-side gap items for review.

## Required request fields

- `target_store_id`
- `reference_category_id`
- `target_category_ids` — non-empty array

## Optional request fields

- `search`
- `only_available`
- `statuses`

## Validation rules

The endpoint must reject requests where:

- `target_store_id` is missing;
- `reference_category_id` is missing or invalid;
- `target_category_ids` is empty;
- any requested target category is not mapped to the selected reference category.

## Semantics

The response includes target products that:

- belong to the selected target store;
- belong to the selected mapped target categories;
- are not in confirmed mappings;
- are not included in candidate match groups.

## Status filtering rules

- default visible statuses are `new` and `in_progress`;
- `done` may be filtered out by default from visible groups;
- `done` must still contribute to summary counts.

## Response model

The response should include:

- selected reference category metadata;
- selected target store metadata;
- selected target categories;
- summary counts by status;
- grouped items by target category.

## `POST /api/gap/status`

Persists review state for a gap item.

## Required request fields

- `reference_category_id`
- `target_product_id`
- `status`

## Allowed statuses

- `in_progress`
- `done`

## Rejected status

- `new`

`new` is implicit and represented by the absence of a persistence row.

## Semantics

- updating to `in_progress` or `done` creates or updates the sparse status record;
- a unique status row exists per `(reference_category_id, target_product_id)`;
- the endpoint should return the resulting persisted state.

## Non-goals of the DB-first API family

The following do **not** belong here:

- category synchronization;
- product synchronization;
- registry-to-DB store synchronization;
- debug parsing helpers;
- live scraping utilities.

Those must remain documented separately to preserve the boundary between supported read flows and operational/internal flows.
