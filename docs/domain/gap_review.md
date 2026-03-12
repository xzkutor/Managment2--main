# Gap Review Specification

## Status

Draft. This document formalizes the `/gap` workflow for assortment-gap review.

## Purpose

The gap page exists for content managers who need to review **target-store products missing from the reference assortment context**.

README describes `/gap` as a dedicated page for reviewing products that:
- are not in confirmed `ProductMapping`;
- do not appear in any candidate lists.

That statement is the core business definition of a gap item.

## Context Model

A gap review request is defined by:
- one target store;
- one reference category;
- one non-empty set of target categories mapped to that reference category;
- optional search and availability filters;
- visible statuses.

## Entry Preconditions

The workflow is only valid when category mappings exist for the chosen reference category.

If mappings do not exist:
- UI should block loading the page data;
- API should reject invalid requests.

## Core Definition

For a given context, a target product is a **gap item** if it is inside the selected target scope and is neither:
- confirmed as equivalent through `ProductMapping`;
- nor present in any candidate list for the current comparison logic.

This means the gap set is contextual, not universal.

## API

### `POST /api/gap`

Returns grouped gap items for the requested context.

### Required fields
- `target_store_id`
- `reference_category_id`
- `target_category_ids` (non-empty)

### Optional fields
- `search`
- `only_available`
- `statuses`

### Validation rules
- target store must exist;
- reference category must exist;
- target category list must be non-empty;
- every target category id must belong to the mapping set for the chosen reference category;
- invalid category scope yields `400`.

## Response Semantics

The response includes:
- the resolved reference category;
- the resolved target store;
- selected target categories;
- overall summary counters;
- grouped items per target category.

Grouping by target category is part of the product contract because it supports operational review and batch understanding.

## Status Model

README defines three effective statuses:

- `new`
- `in_progress`
- `done`

### Persistence rule
Only non-default states are stored in the database.

Therefore:
- `new` is implicit and represented by the absence of a DB row;
- `in_progress` is persisted;
- `done` is persisted.

This is a critical domain invariant.

## Status transitions

Allowed operational transitions:

- `new` → `in_progress`
- `in_progress` → `done`

Optional future transitions may be added explicitly, but they are not part of the currently documented contract.

### `POST /api/gap/status`

Persists review status for a target product under a reference category context.

### Required fields
- `reference_category_id`
- `target_product_id`
- `status`

### Allowed status values
- `in_progress`
- `done`

### Disallowed status value
- `new`

`new` must not be accepted as an input value because it is implicit.

## Summary Semantics

The summary object reports totals for:
- total
- new
- in_progress
- done

README makes one subtle but important rule explicit:

`done` may be hidden from the item list by default, but it is still counted in summary totals.

That means:
- visibility filter affects listed items;
- summary represents overall state of the contextual gap universe.

## Availability / Search Filters

### `search`
Filters by case-insensitive substring match on product name.

### `only_available`
Restricts results to available products.

These filters narrow the visible item set but do not change the underlying domain meaning of a gap item.

## Uniqueness / Identity

The persisted status table is unique by:
- `reference_category_id`
- `target_product_id`

This means review state is stored per reference-category context, not as a global target-product state.

That design is correct because the same target product may have different review meaning under different reference contexts.

## Operational UX Expectations

The gap page should make the following visible:
- context header;
- grouped sections by target category;
- summary counters;
- actionable buttons for status transitions;
- sensible defaults for visible statuses.

README states that default visible statuses are `new` + `in_progress`, with `done` hidden by default.

## Relationship to Comparison

Gap is downstream from comparison logic.

If comparison heuristics change, the computed gap set may change too because candidate coverage changes.

Therefore:
- gap behavior depends on comparison semantics;
- docs for gap and comparison must stay aligned.
