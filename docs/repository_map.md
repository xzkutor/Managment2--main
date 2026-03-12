# Repository Map

## Purpose

This document describes the current repository layout, ownership boundaries between modules, and the intended direction for further cleanup. It is a repository navigation document, not a runtime specification.

## Top-Level Layout

### `app.py`
Current Flask entrypoint and route composition layer.

Responsibilities currently include:
- application bootstrap / app factory wiring;
- registration of UI pages;
- registration of API routes;
- orchestration between service layer functions and HTTP handlers;
- some legacy/debug-facing routes that should remain explicitly isolated.

Target direction:
- keep app bootstrap here or in a dedicated factory module;
- gradually move route groups into blueprints or route modules by bounded area.

### `pricewatch/`
Primary application package.

Expected responsibility split inside the package:
- `core/` — shared primitives, normalization, matching helpers, registry plumbing, cross-cutting utilities;
- `db/` — persistence models, repositories, database abstractions, transactional helpers;
- `services/` — application use-cases and orchestration flows such as sync, mapping, comparison, and gap review;
- `shops/` — adapter implementations for individual external sources;
- additional package modules — focused helpers that do not belong in app.py.

### `migrations/`
Schema migration history and Alembic runtime configuration.

Rules:
- schema changes must be represented here;
- migrations are append-only except in pre-release rewrite situations explicitly approved by maintainers;
- documentation should reference semantic schema intent rather than migration internals.

### `tests/`
Executable specification of expected behavior.

Current role:
- API contract validation;
- adapter contract validation;
- comparison and gap behavior validation;
- repository/database behavior validation;
- normalization and registry validation.

Target role:
- remain the final enforcement layer after docs/spec updates.

### `templates/`
Server-rendered HTML templates for UI pages such as `/`, `/service`, and `/gap`.

### `static/`
CSS, JS, image, and other browser-consumed assets.

### Root documentation files
Examples:
- `README.md`
- `CONTRIBUTING.md`
- repo-facing support documents

Root files should stay lightweight and navigational. Stable detailed specs belong in `docs/`.

## Logical Module Boundaries

### UI Layer
Includes:
- HTML page routes;
- template rendering;
- page-specific JS/CSS coordination.

Should not contain:
- scraping adapter logic;
- direct persistence policy beyond invoking service/repository abstractions;
- matching heuristics implementation details.

### API Layer
Includes:
- request validation and response shaping;
- HTTP status mapping;
- stable contract surfaces.

Should not contain:
- domain policy encoded inline in route functions when it can live in service/domain layer.

### Service Layer
Includes:
- sync workflows;
- mapping workflows;
- comparison generation;
- gap review updates;
- orchestration across adapters, repositories, and domain helpers.

Should not contain:
- framework-specific rendering concerns;
- adapter-specific parsing rules that belong inside adapter implementations.

### Domain / Core Layer
Includes:
- normalization rules;
- matching heuristics;
- scoring semantics;
- state derivation rules;
- shared value conventions.

Should be deterministic and test-friendly.

### Persistence Layer
Includes:
- ORM models / schema bindings;
- repositories;
- DB queries;
- persistence invariants.

Should not own UI/runtime-only state unless explicitly persisted by design.

### Adapter Layer
Includes:
- per-store scraping/fetching/parsing;
- external-source normalization into internal adapter contract;
- adapter capability declaration.

Should not define product truth semantics beyond adapter contract.

## Runtime Flows by Area

### 1. Catalog sync flow
Adapter → service orchestration → repositories → persisted categories/products/scrape runs.

### 2. Mapping management flow
Admin/service action → candidate inspection and/or confirmation → persisted category/product mappings.

### 3. Comparison flow
DB-first read path → comparison assembly → UI/API response.

### 4. Gap review flow
Comparison-derived gap set → state resolution using persisted override statuses → `/gap` UI/API presentation.

## Cleanup Guidance

### Priority 1
- keep `docs/` as source of truth for stable specs;
- reduce root README scope;
- clearly mark legacy/debug endpoints.

### Priority 2
- split route registration into focused route modules or blueprints;
- make service boundaries easier to discover from import graph.

### Priority 3
- add repository map links from README and CONTRIBUTING;
- maintain code-owner hints if team size grows.

## Ownership Principle

Every non-trivial behavior should be attributable to one primary home:
- HTTP contract → API docs + route layer;
- domain rule → domain docs + domain/core tests;
- persistence rule → migration/schema/repository docs;
- external-source handling → adapter contract + adapter tests.

Ambiguous ownership is treated as documentation debt.
