# Domain Invariants

## Scope

This document defines stable business rules for the current project domain.

## Core entities

### Store
A store is a source system from which categories and products are collected.

Invariants:
- a store represents one logical catalog source
- stores must be synchronized from the adapter registry before category/product sync can be reliable
- a store may act as reference or target in comparison flows

### Category
A category belongs to exactly one store.

Invariants:
- category names are store-local, not globally unique
- comparison is not allowed unless the selected reference category has target mappings
- category mappings are the entry point into comparison

### Product
A product belongs to exactly one category and, transitively, one store.

Invariants:
- a product is compared only inside the context of mapped categories
- persisted product data is the source of truth for UI comparison
- product freshness depends on sync lifecycle, not on user comparison requests

### CategoryMapping
A category mapping links one reference category to one target category.

Invariants:
- mappings are many-to-many across the system
- comparison is allowed only for mapped category pairs
- the identity of a mapping pair is immutable after creation
- mutable fields are metadata such as confidence or match type, not the linked pair itself

### ProductMapping
A product mapping is a confirmed cross-store match.

Invariants:
- confirmed matches are persisted truth
- runtime candidates are not persisted as mappings
- once confirmed, a product pair must be excluded from “gap” output for the same context

### ScrapeRun
A scrape run records execution of synchronization work.

Invariants:
- sync operations should create history records
- history is operational evidence, not business content
- user-facing comparison should not require inspecting scrape run history to function

### GapItemStatus
A gap item status stores manual workflow state for target-only products in a reference-category context.

Invariants:
- status is contextual to `(reference_category_id, target_product_id)`
- `new` is implicit and means “no persisted status row”
- only non-default workflow states are stored
- accepted stored statuses are `in_progress` and `done`

## Comparison invariants

- comparison is DB-first
- comparison is mapping-driven
- candidate matches are computed at runtime
- confirmed matches are persisted
- target-only items are not the same thing as gap items until evaluated in the selected reference-category context

## Gap invariants

A product appears in gap review when it is:
- in the selected target category scope
- not covered by confirmed `ProductMapping`
- not included in candidate groups for the selected comparison context

Additional rules:
- default visible statuses are `new` and `in_progress`
- `done` may be hidden from the main list but still counted in summary
- gap review is a manual workflow layer, not an automatic deletion or suppression layer

## Freshness invariants

- stale data is an operational state, not a domain identity
- users should be guided to `/service` when refresh is needed
- the system should not silently switch from DB-backed comparison to live scraping to compensate for stale DB data
