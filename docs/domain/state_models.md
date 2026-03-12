# State Models

## Purpose

This document captures stateful concepts used by the system and how those states are derived, persisted, or interpreted.

## State Model Inventory

The system contains multiple kinds of state:
- persisted catalog state;
- persisted mapping state;
- persisted scrape-run state;
- persisted override state for gap review;
- runtime-derived comparison state;
- runtime-derived candidate matching state.

The critical rule is that not every visible UI state is a first-class persisted state machine.

## 1. Catalog Freshness State

### Nature
Derived state.

### Inputs
- last successful sync time;
- scrape run metadata;
- presence/absence of current category/product data.

### Example interpretations
- fresh;
- stale;
- unknown.

### Persistence
Freshness may be computed from persisted timestamps and run data rather than stored as a dedicated enum.

### Rule
Derived freshness must not be allowed to silently redefine product or mapping truth.

## 2. Scrape Run State

### Nature
Persisted state.

### Canonical lifecycle
Typical phases:
- created / queued
- running
- succeeded
- failed

Actual field names may vary by implementation, but documentation and code should preserve the distinction between successful completion and partial/failed execution.

### Transitions
- created → running
- running → succeeded
- running → failed

Optional future transitions:
- queued → cancelled
- running → cancelled

### Invariants
- terminal states are immutable except for post-run annotation fields;
- timestamps must support post-mortem inspection;
- run state should not be overloaded to represent mapping/business review status.

## 3. Category Mapping State

### Nature
Persisted truth state.

### Minimal state model
A category mapping is either:
- absent;
- present (confirmed).

There is no requirement for a persisted “candidate” category mapping state unless explicitly introduced later.

### Invariants
- persisted mapping means the system treats the relation as confirmed truth;
- runtime suggestions must not be mistaken for persisted mappings.

## 4. Product Mapping State

### Nature
Persisted truth + runtime suggestion overlay.

### Persisted states
- absent
- present (confirmed)

### Runtime-only suggestion states
- candidate
- ambiguous candidate set
- no candidate

### Rule
Only confirmed mappings are durable business truth. Candidate outputs are ephemeral decision-support artifacts.

## 5. Comparison Item State

### Nature
Runtime-derived presentation state.

### Common interpretations
- matched
- higher price on compared store
- lower price on compared store
- missing on compared store
- ambiguous

### Persistence
Not persisted as canonical state unless a future feature explicitly snapshots comparison results.

### Invariants
- comparison result state is recalculated from DB truth plus current query/filter context;
- it must not be used as a hidden substitute for product mapping state.

## 6. Gap Review State

### Nature
Mixed model: runtime-derived item + persisted override status.

### Visible UI states
- `new`
- `in_progress`
- `done`

### Persistence rule
- `new` is implicit and derived from absence of explicit persisted override;
- only non-default statuses are stored explicitly.

### Transitions
- `new` → `in_progress`
- `new` → `done`
- `in_progress` → `done`
- `done` → `in_progress` when reopened
- explicit record removal may revert item to implicit `new` if supported by implementation

### Invariants
- status is contextual to the gap-review domain, not universal product lifecycle state;
- status must not mutate source catalog/product truth.

## 7. UI Workflow State

### Nature
Ephemeral client/server interaction state.

Examples:
- selected store/category filters;
- active service tab;
- current gap filter;
- temporary form draft state.

### Persistence
Out of scope unless implementation stores user preferences explicitly.

## 8. Error / Failure State

### Nature
Mixed.

Some failures are persisted indirectly through scrape runs; others are transient request/response conditions.

Examples:
- sync failure captured in run history;
- validation error returned by API and not persisted;
- adapter parsing issue surfaced in debug endpoint.

## Modeling Principles

### Persist only durable business truth
Examples:
- stores/categories/products;
- confirmed mappings;
- scrape runs;
- non-default gap statuses.

### Derive presentation state when possible
Examples:
- comparison badges;
- implicit `new` gap items;
- freshness labels.

### Keep state-machine boundaries separate
Do not overload one state system to answer another domain question.

Examples of invalid mixing:
- using scrape run status as product availability status;
- using gap status as mapping confirmation status;
- using comparison result flags as persisted mapping truth.
