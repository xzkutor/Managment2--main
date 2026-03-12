# Gap Review

## Purpose

The `/gap` workflow is intended for manual review of assortment gaps by content or catalog managers.

## Concept

A gap item is a target-side product in the selected context that is not currently represented in the reference assortment through either:
- confirmed product mappings
- runtime candidate groups

This is a review concept, not a raw storage concept.

## Required context

Gap review requires:
- target store
- reference category
- at least one mapped target category

If target categories are not mapped to the selected reference category, the workflow should be blocked and the user should be redirected to mapping setup in `/service`.

## Usage scenario

1. Select **target store** (not reference).
2. Select **reference category**.
3. Mapped target categories load — all checked by default.
4. If no mappings exist — loading is blocked with a hint to go to `/service`.
5. Set filters (search, "in stock only", statuses) and click **"Show gap"**.
6. Results are grouped by target category with summary cards.

## Status model

### `new`
- implicit
- not stored in DB
- means "not reviewed yet"

### `in_progress`
- stored in DB
- means the item is currently being worked on

### `done`
- stored in DB
- means review work is complete

## Status transitions

| Button | Transition |
|---|---|
| **"Take to work"** | `new` → `in_progress` |
| **"Mark done"** | `in_progress` → `done` |

## Default visibility

- Visible by default: `new` + `in_progress`.
- `done` is hidden by default but is **always counted in summary**.

## Invariants

- the same target product may have different statuses under different reference categories
- status belongs to review workflow, not to the product globally
- `done` items may be hidden by default but must remain countable in summary
- `new` status is **never** accepted as an API input (it is implicit — absence of a DB row)

## Reviewer actions

Typical actions:
- load gap context
- filter by search and availability
- take an item into work
- mark an item as done

## Non-goals

Gap review is not:
- automatic catalog synchronization
- automatic product creation on the reference side
- a replacement for product mappings
- a full editorial workflow engine
