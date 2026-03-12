# Contributing

This document defines the working conventions for contributors to the project.
It does not replace architectural or API documentation from `docs/`; instead, it explains how changes should be prepared, validated, and documented.

## Scope

This repository contains:

- Flask application entrypoints and routes
- DB-backed comparison flows
- store/category/product mapping logic
- scraper adapter integrations
- migrations and test suite
- templates/static assets for user-facing and service/admin UI

Contributors must preserve the current architectural direction:

- main product flow is DB-first
- external shop scraping is integration-layer behavior
- confirmed mappings are persisted truth
- runtime candidates are advisory only
- gap review is an operational workflow with its own state model

## Change categories

### 1. Domain changes

Examples:

- new mapping rules
- comparison semantics changes
- gap-state logic changes
- schema/model invariant changes

Required alongside code changes:

- update relevant files in `docs/domain/`
- add or update tests that encode the invariant
- mention migration impact explicitly if persistence changes

### 2. API changes

Examples:

- request/response contract changes
- endpoint additions/removals
- admin/service route changes

Required alongside code changes:

- update the matching file in `docs/api/`
- preserve clear separation between DB-first, admin/service, and internal/legacy APIs
- document whether the change is backward-compatible

### 3. Integration changes

Examples:

- new scraper adapter
- adapter registry changes
- shop-specific extraction logic

Required alongside code changes:

- update `docs/integrations/adapter_contract.md`
- add adapter-focused tests
- avoid leaking shop-specific assumptions into domain/core layers

### 4. Operational changes

Examples:

- sync lifecycle changes
- new manual review flows
- new runbook-worthy maintenance steps

Required alongside code changes:

- update `docs/operations/`
- document failure modes and operator expectations

## Branch and commit expectations

Prefer small, reviewable commits.

Recommended commit structure:

1. schema/model changes
2. repository/service logic
3. route/controller updates
4. tests
5. documentation

When a change spans all layers, keep docs in the same PR and do not defer documentation to “later”.

## Testing expectations

Before opening or merging a change, run the relevant test subset and the full suite when touching cross-cutting behavior.

At minimum, contributors should validate:

- repository behavior for persistence-related changes
- API contract tests for route changes
- comparison/gap tests for business-rule changes
- adapter tests for scraper integration changes

Refer to `docs/testing/testing_strategy.md` for the full testing guidance.

## Documentation rules

Documentation is part of the deliverable.

A change is incomplete when it modifies one of the following without updating docs:

- domain invariants
- API contract
- operator workflow
- architecture boundaries
- adapter integration contract

### Source-of-truth policy

- `docs/architecture/` explains structure and boundaries
- `docs/domain/` explains invariants and business semantics
- `docs/api/` explains externally or internally consumed contracts
- `docs/integrations/` explains adapter/plugin contracts
- `docs/operations/` explains sync and maintenance procedures
- tests enforce behavior and should align with the above

The root `README.md` should remain an overview and navigation entrypoint, not the only place where the system is specified.

## Review checklist

Before merging, reviewers should verify:

- architecture boundaries are preserved
- DB-first behavior remains the default for main comparison flow
- no new persistent semantics are introduced without documentation
- legacy/debug endpoints are not expanded into product-facing contract accidentally
- tests reflect the claimed behavior
- docs were updated where needed

## Anti-patterns to avoid

Avoid the following unless there is an explicit ADR or approved refactor plan:

- putting new core business logic directly into a large route/controller file
- coupling comparison logic to live scraping
- storing runtime candidate matches as if they were confirmed mappings
- treating gap status rows as a complete set of all visible gap items
- adding product-facing dependencies on legacy/debug endpoints
- encoding critical invariants only in README prose without docs/tests alignment
