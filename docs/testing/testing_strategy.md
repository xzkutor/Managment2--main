# Testing strategy

## Purpose

This document defines how the repository test suite should be interpreted and extended.
The project already relies heavily on tests as an executable specification. The goal of this document is to make that explicit and reduce the risk that behavior is only discoverable through reading tests.

## Testing layers

### 1. Unit tests

Unit tests should validate isolated behavior such as:

- normalization helpers
- matching heuristics
- adapter parsing helpers
- repository-level transformations
- registry behavior

These tests should be fast, deterministic, and avoid unrelated I/O.

### 2. Repository / persistence tests

Repository tests validate:

- schema-backed persistence assumptions
- read/write semantics for stores, categories, products, mappings, scrape runs, history
- gap status persistence semantics
- uniqueness, idempotency, and upsert-like behavior where applicable

These tests are the practical guardrail around DB-first architecture.

### 3. API contract tests

API tests validate stable request/response behavior for:

- DB-first UI/API flows
- service/admin endpoints
- mapping operations
- comparison endpoints
- gap workflow endpoints

Where a route is internal, legacy, or debug-oriented, the test should make that status obvious rather than treating it as a public contract.

### 4. Integration / adapter tests

Adapter tests validate the contract between the application and each shop-specific scraper.

They should cover:

- category discovery shape
- product extraction shape
- normalization assumptions
- edge cases around missing or malformed fields
- deterministic interpretation of source shop data

### 5. End-to-end workflow tests

Where feasible, the suite should cover the main workflows:

- sync data into DB
- review mapping/gap state
- run comparison from DB-backed data
- inspect history/stateful outputs

These tests do not need to reproduce full production conditions, but they should validate the intended layered behavior.

### 6. Frontend tests (Vitest + @vue/test-utils)

Frontend tests live under `frontend/src/test/` and are run with:

```bash
cd frontend && npm test
```

Coverage areas:

| Path | What it covers |
|---|---|
| `test/router/` | SPA router contract: canonical routes resolve to named routes, catch-all renders `not-found`, route meta is present |
| `test/components/` | Shared Vue components: structure, props, accessibility attributes (`aria-current`) |
| `test/composables/` | Shared composables: `useAsyncState` loading/error states |
| `test/pages/*/` | Page-level composable logic and component rendering |
| `test/api/` | `requestJson` wrapper and `ApiError` class |

**Conventions:**
- Mock API modules at the top of each test file using `vi.mock(...)`.
- Use `flushPromises()` after async operations.
- Test composables directly for logic coverage.
- Test components for rendered output, emitted events, and prop-driven state.
- Router tests use `createMemoryHistory()` — never `createWebHistory()` in tests.

**CI requirement:** `npm run typecheck` and `npm test` both run in CI (`.github/workflows/python-app.yml`). A failing frontend typecheck or test is a blocking CI failure.

## Test design principles

### Behavior over implementation

Tests should describe what the system guarantees, not how the current implementation happens to work.

### Domain vocabulary

Use domain terms consistently in test names and fixtures:

- confirmed mapping
- candidate match
- DB-first comparison
- gap item
- implicit `new` status
- scrape run

### Determinism

Avoid tests that depend on unstable external shop behavior unless explicitly marked as optional/manual.
Mainline CI tests should not depend on live scraping targets.

### Small fixtures, explicit semantics

Fixtures should stay small and readable.
When a fixture encodes a domain rule, add a comment or naming convention that makes the business meaning obvious.

## Minimum coverage by change type

### Domain-rule changes

Required:

- unit or service-level test for new rule
- repository/API test if persistence or route-visible behavior changes
- regression test for the previous failure or ambiguity

### API changes

Required:

- request/response test
- error-handling test
- compatibility test when old behavior is intentionally preserved

### Schema changes

Required:

- migration validation where practical
- repository tests for new persistence behavior
- round-trip tests for read/write semantics

### Adapter changes

Required:

- adapter contract tests
- parsing edge-case tests
- registry wiring test if a new adapter is added

## Test suite as executable spec

Parts of the current system behavior are discoverable in tests before they are fully documented in prose.
This is useful, but it should not remain the only source of truth.

Rule:

- tests enforce behavior
- `docs/` explains intended behavior
- code implements behavior

When these diverge, the discrepancy must be resolved explicitly.

## CI expectations

CI should fail on:

- broken invariants
- changed route contract without test updates
- adapter output regressions
- repository persistence regressions

A green CI run is necessary but not sufficient; reviewers must still verify that documentation and architecture boundaries remain correct.
