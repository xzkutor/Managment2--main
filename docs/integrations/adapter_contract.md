# Adapter Contract

## Purpose

This document defines the minimum expectations for store adapters used by the registry.

## Role of an adapter

An adapter encapsulates store-specific scraping/parsing logic and exposes normalized outputs to the rest of the system.

The rest of the application should not need to know site-specific parsing details.

## Required capabilities

An adapter should be able to provide:

- identity / registry metadata
- category discovery for its store
- product extraction for a selected category or category URL
- stable enough product attributes for persistence and comparison

## Output expectations

### Category output
A category record should be normalizable into:
- store-local identifier or stable source key when available
- display name
- source URL when relevant

### Product output
A product record should be normalizable into:
- name
- URL
- price and currency when available
- availability when available
- source-specific identifier/article/model fields when available

## Contract rules

- adapters return normalized data shapes, not presentation HTML
- adapter failures must be surfaced as sync failures, not silently swallowed
- network/retry policy belongs to the integration boundary, not to comparison logic
- adapters should not persist directly to the database; services own persistence

## Registry rules

- adapters are discovered and selected through the registry
- store synchronization should reflect registry truth into the DB
- domain/source routing belongs to registry selection, not to UI code

## Testing expectations

Each adapter should be covered by:
- contract tests for output shape
- parsing tests using realistic fixtures when possible
- failure-path tests for changed markup or unavailable pages

## Evolution guidance

When adding a new adapter:
1. implement adapter contract
2. register it
3. ensure store sync can materialize it into DB
4. add tests before relying on it in UI flows
