# ADR-0003: Gap status model with implicit `new`

- Status: Accepted
- Date: 2026-03-12

## Context

The gap workflow identifies assortment gaps between reference and compared stores. Operators need to track review progress, but the system should avoid storing redundant state for every discovered gap candidate.

## Decision

The gap workflow uses an implicit-default status model:

- `new` is the default conceptual status
- `new` is not stored explicitly by default
- only non-default review states are persisted, specifically `in_progress` and `done`

## Rationale

Most discovered gap items start in the same default state. Persisting a database row for every untouched gap item adds storage and lifecycle noise without adding meaningful information.

Using implicit `new` preserves clear semantics while minimizing redundant records.

## Consequences

### Positive

- Cleaner persistence model with fewer redundant rows.
- Simpler interpretation of untouched gap items.
- Easier reset behavior: absence of an override naturally means `new`.

### Negative

- Consumers must understand that missing persisted status is meaningful.
- Query logic must merge persisted overrides with default semantics.

## Interpretation rule

For any gap item:

- if no persisted status row exists, effective status is `new`
- if a persisted row exists, effective status is the stored non-default state

## Scope

This ADR governs review state semantics for gap items. It does not define how gap candidates are discovered, ranked, or presented.

## Alternatives considered

### Persist all statuses including `new`

Rejected because it introduces unnecessary rows for the default untouched case and makes the dataset more verbose without improving domain meaning.

### Use a separate boolean reviewed flag

Rejected because the workflow needs at least three meaningful conceptual states: untouched, in progress, and done.

## Review trigger

Revisit if the workflow requires richer state transitions such as dismissed, deferred, reopened, or assignment metadata that materially changes the review model.
