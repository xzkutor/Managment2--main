# ADR-0005: Contain legacy/debug endpoints outside the stable product contract

- Status: Accepted
- Date: 2026-03-12

## Context

The codebase contains endpoints and utilities that are useful for diagnostics, parser development, exploratory scraping, and legacy workflows. These capabilities may be valuable operationally, but they do not have the same stability expectations as the supported product-facing API.

Without an explicit decision, internal/debug paths risk becoming de facto public contract.

## Decision

Legacy and debug endpoints are explicitly contained outside the stable product contract.

This means:

- they must be documented separately from supported DB-first and admin/service APIs
- they must not define the product’s primary semantics
- compatibility guarantees for them are weaker unless explicitly upgraded into supported API status

## Rationale

The project needs room to keep useful diagnostic tools without letting them distort architectural boundaries or external expectations.

## Consequences

### Positive

- Supported API can remain clear and stable.
- Internal experimentation can continue without overcommitting to backward compatibility.
- Migration away from legacy behavior becomes easier to plan.

### Negative

- Some consumers may need migration guidance if they relied on informal behavior.
- Teams must enforce labeling and documentation discipline.

## Required documentation rule

All such endpoints must be grouped under dedicated internal/legacy documentation and clearly labeled as non-primary product interfaces.

## Alternatives considered

### Treat all existing endpoints as equally supported

Rejected because it blurs the contract surface and makes future cleanup much harder.

### Remove all debug endpoints immediately

Rejected because they may still provide operational value during transition and development.

## Review trigger

Revisit when an endpoint currently considered legacy/debug becomes necessary for stable external consumption and should be promoted into supported API status.
