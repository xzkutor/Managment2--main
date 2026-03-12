# Documentation Conventions

## Goal

Keep documentation focused, non-duplicative, and close to the real system boundaries.

## Language rules

- The root `README.md` should remain in the current project language.
- Internal technical specs under `docs/` may remain in English unless the repository adopts a different convention later.
- Do not mix languages inside the same section unless there is a strong reason.

## Writing rules

- Prefer explicit scope statements at the top of each document.
- Separate supported behavior from internal or debug behavior.
- Use stable domain terminology consistently.
- Avoid copying route details into multiple files.
- Prefer linking to the source-of-truth document instead of duplicating detailed explanations.

## Structure rules

Recommended internal structure:

- `docs/architecture/` for high-level system structure
- `docs/domain/` for invariants, semantics, and state models
- `docs/api/` for endpoint contracts and classification
- `docs/integrations/` for adapter boundaries and contracts
- `docs/operations/` for workflows and runbooks
- `docs/testing/` for strategy and test taxonomy
- `docs/adr/` for durable decisions
- `docs/decisions/` for still-open questions

## File naming

- Use lowercase snake_case file names (to match existing docs like `comparison_and_matching.md`)
- Keep file names descriptive and stable
- Number ADR files sequentially with a short snake_case slug

## Document template guidance

A good technical document usually includes:

1. Purpose or scope
2. Definitions or context
3. Current behavior
4. Constraints and invariants
5. Edge cases or exclusions
6. Follow-up links to related docs

## What not to do

- Do not treat tests as the only specification.
- Do not document legacy behavior as the default unless it is still supported.
- Do not let root `README.md` become the only place where architecture and API truth lives.
- Do not describe runtime-derived data as persisted truth.
