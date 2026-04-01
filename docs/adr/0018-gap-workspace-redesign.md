# ADR-0018: Gap Workspace Redesign

- **Status:** Proposed
- **Date:** 2026-03-30
- **Related ADRs:** ADR-0015 (Full SPA Transition), ADR-0016 (Comparison Workspace Redesign), ADR-0017 (Matches Workspace Redesign)
- **Related RFC:** To be created after open questions are resolved

## Context

The `/gap` page has already been migrated into the SPA, but its current UX still follows the legacy page-form pattern rather than the workspace pattern now used as the target direction for the application.

Current structure in the repo:

- `frontend/src/pages/gap/GapPage.vue` renders a vertical page stack
- `GapFilters.vue` contains a dense filter form with cascading selectors, mapped target category checkboxes, search, availability, status filters, and the primary action
- `GapSummary.vue` renders summary cards after data is loaded
- `GapStatusBanner.vue` renders loading, error, and empty states separately from the main result area
- `GapGroupTable.vue` renders grouped result blocks after a successful request
- `useGapFilters.ts`, `useGapData.ts`, and `useGapActions.ts` already separate state ownership well enough to support a view-level redesign without requiring a backend rewrite

This results in a page that is functionally correct but visually fragmented:

- filters feel like a form, not a persistent operator control surface
- the main work area is visually empty before the first run
- summary, status, and grouped results do not read as one coherent workspace
- loading/error/empty states interrupt the flow instead of belonging to the work surface
- the page does not yet align with the emerging SPA design language used for `/comparison` and `/matches`

## Decision

Redesign `/gap` as a **workspace-style page** with a stable two-column structure:

- **Left sticky control rail**
  - target store selector
  - reference category selector
  - mapped target categories panel
  - search input
  - availability filter
  - status filters
  - primary action: `Показати розрив`

- **Right work surface**
  - context/header strip
  - KPI/summary row
  - pre-load placeholder before the first run
  - loading / error / empty states rendered inside the work surface
  - grouped result blocks, one panel per mapped target category group

The redesign keeps the current behavior model:

- target store is selected explicitly by the operator
- reference category is selected explicitly by the operator
- mapped target categories are derived from mappings and can still be selectively included via checkboxes
- search, availability, and status filters remain part of the `/gap` workflow
- `useGapData.ts` continues to preserve visible results during reloads
- row-level status mutations continue to use the existing no-blanking local patch pattern where possible

## Consequences

### Positive

- `/gap` becomes visually aligned with `/comparison` and `/matches`
- the page gets a persistent operator-oriented structure instead of a one-shot filter form
- the main panel will no longer show confusing empty whitespace before the first request
- status, loading, empty, and grouped results can be understood as one work surface
- the redesign can be implemented mainly in the Vue layer without requiring a broad backend rewrite

### Negative / Trade-offs

- several presentational components will need to be restructured, not just restyled
- filter density and responsive behavior will need deliberate treatment to avoid an oversized left rail
- grouped result panels may need compaction work in `GapGroupTable.vue`
- test coverage will need updates because layout and state presentation rules will change

## Non-goals

This ADR does **not** propose:

- changing the `/api/gap` contract as a prerequisite
- removing mapped target category selection from the workflow
- redesigning the global SPA shell or sidebar
- introducing Pinia-specific state ownership for `/gap`
- changing business rules for gap statuses (`new`, `in_progress`, `done`)

## Design principles

1. **Workspace, not form page**  
   Filters stay visible and stable while results change on the right.

2. **No meaningless empty canvas**  
   Before the first run, the right panel must show a clear placeholder with guidance.

3. **Results own the right side**  
   Summary, status messaging, and grouped blocks belong to the same work surface.

4. **Mutation stability**  
   Status actions must not cause full-page visual resets.

5. **Consistency with other redesigned pages**  
   `/gap` should feel like part of the same SPA family as `/comparison` and `/matches`.

## Implementation direction

Expected repo touch points:

- `frontend/src/pages/gap/GapPage.vue`
- `frontend/src/pages/gap/components/GapFilters.vue`
- `frontend/src/pages/gap/components/GapSummary.vue`
- `frontend/src/pages/gap/components/GapStatusBanner.vue`
- `frontend/src/pages/gap/components/GapGroupTable.vue`
- `frontend/src/pages/gap/composables/useGapFilters.ts`
- `frontend/src/pages/gap/composables/useGapData.ts`
- `frontend/src/test/pages/gap/*`
- shared CSS / workspace utility styles as needed

## Follow-up

Before implementation, the team should resolve the open UX and rollout questions and then capture the final execution shape in an RFC.
