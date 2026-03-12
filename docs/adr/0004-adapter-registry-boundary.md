# ADR-0004: Adapter registry as the integration boundary for shops

- Status: Accepted
- Date: 2026-03-12

## Context

The project integrates with multiple external shops that may differ in pagination, category structure, product markup, identifiers, and anti-bot behavior.

A stable internal boundary is needed so that new shop integrations can be added without leaking scraper-specific details into comparison, persistence, and UI layers.

## Decision

The system uses a shop adapter registry as the primary integration boundary.

Each supported shop is represented by an adapter implementing the expected shop contract. The rest of the system interacts with supported shops through the registry and adapter interfaces, not through scraper-specific branching scattered across the codebase.

## Rationale

A registry-based adapter boundary:

- isolates scraper variability
- supports incremental addition of shops
- concentrates parsing and external-site behavior in integration modules
- keeps domain and persistence layers stable

## Consequences

### Positive

- Adding a new shop is a bounded task.
- Parser-specific logic remains localized.
- Service orchestration can operate over a common contract.
- Tests can validate shared adapter expectations.

### Negative

- Adapter contract discipline must be maintained.
- Some shop-specific edge cases may require optional capabilities or documented exceptions.

## Required design rule

Domain services, repositories, and user-facing flows must not depend on scraper-specific HTML assumptions. Such assumptions belong inside the adapter implementation or integration helper code.

## Alternatives considered

### Inline shop-specific branching throughout services

Rejected because it increases coupling and makes the codebase harder to evolve.

### One-off scripts outside a shared contract

Rejected as the core architecture because it weakens consistency, testability, and operational reuse.

## Review trigger

Revisit if the project expands beyond shop scraping into a broader ingestion platform where adapters need versioned capabilities, richer metadata contracts, or asynchronous ingestion pipelines.
