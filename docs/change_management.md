# Change Management for Documentation

## Purpose

This document defines how documentation should evolve together with the codebase.

## Rules

1. Any behavior change that affects users, adapters, persistence, or operators must be reflected in `docs/` in the same change set.
2. Any architectural decision that changes boundaries, lifecycle, or persistence semantics must be recorded in a new ADR under `docs/adr/`.
3. Any new endpoint must be classified before merge:
   - DB-first supported API
   - admin/service API
   - internal or debug API
4. Any new persisted state or status must be documented in:
   - `docs/domain/domain_invariants.md`
   - `docs/domain/state_models.md`
5. Any new adapter capability or requirement must update `docs/integrations/adapter_contract.md`.
6. Any operational workflow change must update the corresponding runbook or sync lifecycle document.

## Required documentation review triggers

Documentation updates are required when a change touches any of the following:

- route names, request schemas, response schemas, or endpoint intent
- database schema or migration semantics
- mapping persistence rules
- gap review workflow or statuses
- scraping adapter interface or registry behavior
- sync sequencing and operator actions
- incident handling and failure recovery
- testing strategy or expected fixture behavior

## Review checklist

Before merge, verify:

- the code behavior matches the docs
- the docs do not describe removed behavior as active
- unstable endpoints are not documented as stable contracts
- duplicated explanations are reduced or linked to a single source of truth
- root `README.md` remains concise and repo-facing

## Ownership model

Suggested ownership:

- `docs/api/` — maintainers of routes and handlers
- `docs/domain/` — maintainers of domain logic and repositories
- `docs/integrations/` — maintainers of scraper adapters
- `docs/operations/` — maintainers of sync workflows and service panel behavior
- `docs/adr/` — architecture owners and reviewers

## Versioning approach

The docs are versioned together with the repository.
There is no separate documentation release line.
The current branch state is the source of truth for the current code state.
