# ADR-0002: Persist confirmed mappings; keep candidate matches runtime-only

- Status: Accepted
- Date: 2026-03-12

## Context

The system compares products across stores. Some cross-store relationships are authoritative enough to be persisted, while others are only heuristic suggestions generated at request time.

Without a clear rule, candidate suggestions can become confused with confirmed relationships, and persisted data can accumulate low-confidence noise.

## Decision

The system persists only confirmed mappings as durable truth.

Heuristic candidate matches remain runtime-only unless explicitly promoted through a mapping confirmation workflow.

This applies to:

- product mappings across stores
- category mappings where relevant administrative confirmation exists

## Rationale

The system needs a sharp distinction between:

- **authoritative relation**: a mapping that product logic may rely on
- **heuristic suggestion**: a best-effort output that helps an operator review potential matches

Persisting only confirmed mappings prevents the database from becoming a cache of unstable guesses.

## Consequences

### Positive

- The persisted model remains trustworthy.
- User-facing comparison can rely on durable mappings without interpreting confidence levels on every request.
- Heuristic algorithms can evolve freely without migrating stored candidate data.
- Operator review remains explicit and auditable.

### Negative

- Additional UI and admin workflows are needed to confirm mappings.
- Some plausible matches remain invisible to persisted consumers until reviewed.

## Operational rule

A runtime suggestion may be shown in UI or returned by internal/admin endpoints, but it must not be treated as persisted truth until confirmed.

## Data model implication

Confirmed mappings belong in dedicated mapping tables.

Candidate matches do not require long-term durable storage by default. If temporarily cached for performance or diagnostics, they must be clearly labeled as non-authoritative and disposable.

## Alternatives considered

### Persist all candidate matches with confidence scores

Rejected as the default model because it makes downstream semantics ambiguous and creates maintenance pressure around stale low-confidence records.

### Avoid persisted mappings entirely

Rejected because confirmed cross-store relations are valuable domain knowledge and should survive across runs and sessions.

## Review trigger

Revisit if the product introduces a dedicated probabilistic matching subsystem where confidence-scored relations become a first-class domain concept with explicit downstream semantics.
