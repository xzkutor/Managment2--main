# Admin API Specification

## Status

Draft. This document formalizes the **service/admin** API surface used by the operational UI (`/service`) and by maintenance workflows.

## Purpose

The admin API exists to:
- synchronize store definitions from the adapter registry into the database;
- scrape categories and products into the database;
- manage category mappings;
- inspect scrape history and scrape status.

The admin API is **not** the main end-user read path. The main user flow is DB-first and reads already persisted data.

## Scope

This document covers:
- registry-to-database synchronization;
- category sync;
- product sync;
- category mapping CRUD;
- category auto-linking;
- scrape-runs read API;
- scrape-status polling API.

This document does **not** define:
- DB-first comparison endpoints;
- gap review endpoints;
- debug or legacy scraping endpoints.

## Architectural Role

The service page `/service` is the operational control plane for content synchronization and mapping maintenance. README explicitly describes three tabs:
- Categories
- Mappings
- History

Those tabs map directly to the admin API families described here.

## Endpoint Families

### 1. Store registry sync

#### `POST /api/admin/stores/sync`

Synchronizes adapter registry metadata into the `stores` table.

#### Intent
- discover supported stores from the plugin registry;
- persist them into the database;
- keep store metadata aligned with available adapters.

#### Expected behavior
- idempotent from the caller perspective;
- creates missing stores;
- updates mutable store metadata where appropriate;
- does not delete business data blindly without an explicit cleanup policy.

#### Invariants
- a store is identified by its logical store identity, not by UI label text alone;
- registry is the source of truth for supported stores;
- DB becomes the source of truth for user-facing reads after sync.

---

### 2. Category sync

#### `POST /api/stores/{store_id}/categories/sync`

Scrapes categories from the selected store adapter and persists them.

#### Intent
- populate or refresh categories for one store.

#### Expected behavior
- fetch category list from the adapter for `store_id`;
- normalize category identity according to adapter rules;
- upsert categories into the database;
- create a `scrape_run` or equivalent execution trace for observability.

#### Invariants
- categories belong to exactly one store;
- category sync must not create categories for a different store;
- category names may change over time, but stable identity should be preserved where possible;
- sync is allowed to refresh availability/metadata timestamps.

#### Operational expectations
- safe to rerun;
- should expose enough status to be visible in history/polling UI;
- failures should be observable via scrape history.

---

### 3. Product sync

#### `POST /api/categories/{category_id}/products/sync`

Scrapes products for one category and persists them.

#### Intent
- populate or refresh products under the chosen category.

#### Expected behavior
- resolve category and its store;
- run the proper adapter for that store/category;
- parse and normalize product data;
- upsert products into the database;
- emit scrape history/status information.

#### Invariants
- products belong to exactly one category;
- category belongs to exactly one store;
- sync must not move a product across stores as an incidental side effect;
- product identity must be stable enough to support confirmed mappings and history.

#### Data freshness
- the DB-first UI consumes persisted data only;
- product sync is the mechanism that refreshes this persisted catalog.

---

### 4. Category mappings read/write

README describes category mappings as the prerequisite for comparison and as a many-to-many bridge between reference and target categories.

#### `GET /api/category-mappings`

Returns category mappings.

#### `POST /api/category-mappings`

Creates a mapping.

#### `PUT /api/category-mappings/{id}`

Updates mapping metadata.

#### `DELETE /api/category-mappings/{id}`

Deletes a mapping.

#### Mapping model invariants
- mappings connect **reference category** to **target category**;
- mappings are many-to-many at the system level;
- comparison is allowed only through mapped pairs;
- the category pair itself is immutable after creation;
- mutable fields are metadata such as `match_type` and `confidence`.

#### Validation rules
- both categories must exist;
- mapping pair must be unique;
- reference and target sides must be semantically valid for the business flow;
- duplicate pair creation must fail deterministically.

---

### 5. Category auto-linking

#### `POST /api/category-mappings/auto-link`

Creates candidate mappings automatically, based on exact or normalized category-name equality.

#### Intent
- accelerate bootstrap of mappings after category sync.

#### Invariants
- auto-link is an accelerator, not a replacement for explicit review;
- only eligible categories may be linked;
- normalization rules must be deterministic;
- repeated execution should be idempotent or converge without duplicates.

---

### 6. Scrape history

#### `GET /api/scrape-runs`

Returns paginated scrape history.

#### `GET /api/scrape-runs/{id}`

Returns details for a concrete run.

#### Intent
- provide observability for operational users;
- support the History tab on `/service`.

#### Expected payload concerns
A scrape run should expose enough information to understand:
- what was run;
- against which entity;
- when it started and ended;
- whether it succeeded or failed;
- counts/errors useful for diagnostics.

#### Invariants
- scrape history is append-only from normal API usage;
- historical records should not be rewritten except for completion/finalization fields;
- a completed run must have a terminal status.

---

### 7. Scrape status polling

#### `GET /api/scrape-status`

Returns current or last known scraping state for polling.

#### Intent
- lightweight operational polling from the service page;
- near-real-time feedback while long-running syncs execute.

#### Invariants
- polling endpoint is observational;
- it must not start work;
- it should be consistent with scrape-runs history semantics.

## Error Model

This repo already uses a practical UI-facing API style. The admin API should continue that pattern.

Recommended rules:
- `400` for malformed input or invalid business preconditions;
- `404` when addressed store/category/mapping/run does not exist;
- `409` for uniqueness or state conflicts;
- `500` only for unexpected internal failures.

## Security / Exposure Guidance

Even if the app is currently a single Flask service, admin endpoints should be treated as operational endpoints:
- do not treat them as public unauthenticated internet APIs by default;
- separate them clearly from the DB-first user endpoints in docs and UI;
- avoid mixing admin semantics into the main user page.

## Relationship to Other Docs

- `api_db_first.md` defines the supported read path for end users.
- `comparison_and_matching.md` defines comparison semantics.
- `sync_lifecycle.md` should define run-level sequencing and freshness expectations.
- `api_internal_legacy.md` should document unsupported/live-scrape/debug endpoints.
