# Repository Map

## Purpose

This document describes the current repository layout, ownership boundaries between modules, and the intended direction for further cleanup. It is a repository navigation document, not a runtime specification.

## Top-Level Layout

### `app.py`
Application composition and bootstrap layer.

Responsibilities (current, post-refactor):
- application factory (`create_app`) and Flask/CORS configuration;
- DB engine and scoped-session wiring (per-app-instance, not global);
- `teardown_appcontext` session cleanup;
- store-registry bootstrap sync at startup (non-test mode);
- Blueprint registration via `pricewatch.web.register_blueprints`;
- app-level `after_request` hook (UTF-8 charset enforcement);
- module-level `app = create_app()` as the sanctioned runtime / WSGI / dev entry-point.

`app.py` no longer contains inline route handlers, serializer implementations, or module-level compatibility aliases (`db_session`, `engine`, `SessionFactory`, `registry`).
All route handlers live in `pricewatch/web/` Blueprint modules.

### `pricewatch/`
Primary application package.

Expected responsibility split inside the package:
- `core/` — shared primitives, normalization, matching helpers, registry plumbing, cross-cutting utilities;
- `db/` — persistence models, repositories, database abstractions, transactional helpers;
- `net/` — **canonical HTTP client module** (`pricewatch.net.http_client`). This is the authoritative location for `HttpClient`, `make_default_client`, and `default_client`. Local page caching is a supported part of scraping/runtime infrastructure and lives here. All new code must import from `pricewatch.net.http_client`;
- `services/` — application use-cases and orchestration flows such as sync, mapping, comparison, and gap review;
- `shops/` — adapter implementations for individual external sources;
- `web/` — **Flask web layer** (Blueprints, HTTP context helpers, shared serializers). See below for the detailed breakdown;
- additional package modules — focused helpers that do not belong in app.py.

### `pricewatch/web/`
The web-layer package. Owns all HTTP-boundary code.

| Module | Role |
|---|---|
| `__init__.py` | Exports `register_blueprints(flask_app)` — single entry point for Blueprint registration |
| `context.py` | Web dependency/context helpers (e.g. `get_db_session()`). The **only** place that reads `current_app.extensions` |
| `serializers.py` | Shared, pure response serialization helpers — no DB session or Flask context required |
| `ui_routes.py` | `ui` Blueprint — HTML page routes (`GET /`, `GET /service`, `GET /gap`) |
| `catalog_routes.py` | `catalog` Blueprint — DB-first catalog read endpoints (`GET /api/stores`, `GET /api/categories`, `GET /api/stores/<id>/categories`, `GET /api/categories/<id>/products`, `GET /api/categories/<id>/mapped-target-categories`) |
| `admin_routes.py` | `admin` Blueprint — admin/service endpoints: store sync, category/product sync, category mappings, scrape history, comparison, gap |
| `adapter_routes.py` | `adapters` Blueprint — adapter-facing endpoints (`GET /api/adapters`, `GET /api/adapters/<name>/categories`) |

**Cleanup candidate (later wave):**
`GET /api/categories` in `catalog_routes.py` returns the reference store's categories without a `store_id` path parameter, which is inconsistent with `GET /api/stores/<id>/categories`. It is preserved as-is in this wave and should be addressed in the next cleanup wave.

### `pricewatch/net/`
**Canonical HTTP client module.** Houses `HttpClient`, `make_default_client`, and `default_client`. All new code must import from `pricewatch.net.http_client`. Local page caching is a supported part of scraping/runtime infrastructure and lives here.

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
- HTML page routes (`pricewatch/web/ui_routes.py`);
- template rendering;
- page-specific JS/CSS coordination.

Should not contain:
- scraping adapter logic;
- direct persistence policy beyond invoking service/repository abstractions;
- matching heuristics implementation details.

### API Layer
Includes:
- request validation and response shaping (`pricewatch/web/serializers.py`);
- HTTP status mapping;
- stable contract surfaces;
- Blueprint modules under `pricewatch/web/`;
- web dependency helpers in `pricewatch/web/context.py`.

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
- ~~split route registration into focused route modules or blueprints~~ ✅ done — routes now live in `pricewatch/web/` Blueprint modules;
- address `GET /api/categories` cleanup candidate (inconsistent URL design, noted in `catalog_routes.py`);
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
