# Internal Documentation

This directory is the internal source of truth for the project.

## Purpose

The root `README.md` is useful for onboarding and quick start, but it currently mixes:
- product overview
- setup and launch instructions
- UI flow descriptions
- API contracts
- domain rules
- operational procedures

The purpose of `docs/` is to split those concerns into focused documents with stable ownership.

## Recommended reading order

1. `architecture/overview.md`
2. `domain/domain_invariants.md`
3. `api/db_first.md`
4. `api/admin.md`
5. `domain/comparison_and_matching.md`
6. `domain/gap_review.md`
7. `integrations/adapter_contract.md`
8. `operations/sync_lifecycle.md`
9. `api/internal_legacy.md`

## Documentation rules

- Do not describe unstable or debug endpoints as if they were public contracts.
- Treat the database-backed flow as the primary product flow.
- Keep domain rules in `domain/`, not in UI docs.
- Keep operational runbooks and sync flows in `operations/`.
- Keep adapter requirements in `integrations/`.
- Keep endpoint contracts in `api/`.

## Relationship to root README

The root `README.md` should remain concise and contain:
- project overview
- quick start
- local launch
- pointer to `/service`
- pointer to this `docs/` tree

Detailed API and domain behavior should live here.
