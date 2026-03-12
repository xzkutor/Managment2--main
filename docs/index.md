# Documentation Index

This file is the master index for the internal documentation baseline.

## Start here

1. [`README.md`](../README.md) — quick-start, install, run, API overview tables
2. [`architecture/overview.md`](architecture/overview.md) — layers, flows, principles
3. [`repository_map.md`](repository_map.md) — file/directory map
4. [`domain/domain_invariants.md`](domain/domain_invariants.md) — stable business rules
5. [`api/db_first.md`](api/db_first.md) — full JSON contract for user-facing API

## Architecture and decisions

- [`architecture/overview.md`](architecture/overview.md)
- [`adr/0001-db-first-architecture.md`](adr/0001-db-first-architecture.md)
- [`adr/0002-confirmed-vs-candidate-mappings.md`](adr/0002-confirmed-vs-candidate-mappings.md)
- [`adr/0003-gap-status-model.md`](adr/0003-gap-status-model.md)
- [`adr/0004-adapter-registry-boundary.md`](adr/0004-adapter-registry-boundary.md)
- [`adr/0005-legacy-debug-endpoint-containment.md`](adr/0005-legacy-debug-endpoint-containment.md)

## Domain

- [`domain/domain_invariants.md`](domain/domain_invariants.md)
- [`domain/comparison_and_matching.md`](domain/comparison_and_matching.md) — heuristic algorithm, scoring, dictionaries
- [`domain/gap_review.md`](domain/gap_review.md) — gap workflow, status model, usage scenario
- [`domain/state_models.md`](domain/state_models.md)
- [`glossary.md`](glossary.md)

## API

- [`api/db_first.md`](api/db_first.md) — DB-first endpoints (comparison, gap) with full JSON examples
- [`api/admin.md`](api/admin.md) — service/admin endpoints (sync, mappings, history)
- [`api/openapi_outline.md`](api/openapi_outline.md)

## Operations and integrations

- [`operations/sync_lifecycle.md`](operations/sync_lifecycle.md) — sync flow, DB config, Alembic, DTO contract
- [`operations/runbooks.md`](operations/runbooks.md)
- [`operations/incidents_and_failure_modes.md`](operations/incidents_and_failure_modes.md)
- [`integrations/adapter_contract.md`](integrations/adapter_contract.md)

## Testing

- [`testing/testing_strategy.md`](testing/testing_strategy.md)

## Open items

- [`decisions/`](decisions/)
- [`change_management.md`](change_management.md)
- [`documentation_conventions.md`](documentation_conventions.md)
