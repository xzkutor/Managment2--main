# ADR-0001: DB-first architecture for comparison and review flows

- Status: Accepted
- Date: 2026-03-12

## Context

The project supports multiple shops with heterogeneous scraping adapters and exposes several user-facing and operational flows:

- main comparison flow on the home page
- service/admin workflows for synchronization and mapping management
- gap review workflow for assortment gaps

A core architectural decision is required: whether the user-facing comparison and review flows should read directly from live scrapers on request, or consume persisted normalized data from the database.

## Decision

The system adopts a DB-first architecture for user-facing comparison and review flows.

This means:

- scraping is performed as a separate synchronization step
- adapters normalize external catalog data before persistence
- the main comparison flow reads from persisted data, not directly from a remote shop
- gap review reads from persisted data, not directly from a remote shop
- live scraping endpoints, if retained, are treated as internal/debug capabilities and not as the primary product contract

## Rationale

DB-first architecture provides the following advantages:

1. Predictable user experience. UI requests do not depend on remote shop latency, anti-bot behavior, or transient parser issues.
2. Reproducibility. Comparison results can be explained against a known persisted snapshot.
3. Clear operational boundaries. Sync failures belong to the synchronization plane, not to end-user page rendering.
4. Better testability. Domain logic can be tested against stable persisted fixtures.
5. Extensibility. Additional analytics, history, and review workflows can reuse the same normalized persisted dataset.

## Consequences

### Positive

- User-facing endpoints are more stable and deterministic.
- Comparison logic becomes independent from scraper runtime details.
- Review workflows can store statuses and decisions against persisted entities.
- Historical data and sync runs become meaningful first-class artifacts.

### Negative

- Data freshness depends on synchronization cadence.
- The system must model staleness explicitly.
- Operational tooling is required to run and inspect sync jobs.

## Non-goals

This decision does not prohibit internal live-scrape tools for diagnostics, parser development, or exploratory checks. It only states that such tools are not the main product contract.

## Alternatives considered

### Direct live-scrape on every comparison request

Rejected because it couples the user experience to remote sites, makes results less reproducible, complicates testing, and mixes integration instability with product behavior.

### Hybrid mode with automatic fallback to live scraping

Rejected as a default product behavior because it obscures the source of truth and makes comparison semantics harder to reason about. A controlled internal/debug path is preferable.

## Review trigger

Revisit this ADR if the product intentionally pivots to a real-time comparison model or introduces a distinct real-time subsystem with explicit semantics and UX.
