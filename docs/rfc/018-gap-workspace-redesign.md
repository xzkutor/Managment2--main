# RFC-018: Gap Workspace Redesign

- Status: Draft
- Date: 2026-03-30
- Owner: Product/UI implementation track
- Related: ADR-0015 Full SPA Transition, ADR-0016 Comparison Workspace Redesign, ADR-0017 Matches Workspace Redesign, ADR-0018 Gap Workspace Redesign

## 1. Summary

This RFC proposes a workspace-style redesign of the `/gap` page inside the existing Vue SPA.

The redesign introduces:

- a **left sticky control rail**,
- a **right-side work surface** with context and compact KPI summary,
- a **purposeful placeholder before the first run**,
- **in-surface loading, error, and empty states**,
- **grouped result panels** that remain organized by mapped target category.

The goal is to align `/gap` with the operator-oriented workspace model already adopted for `/comparison` and `/matches`, while preserving current route ownership and current backend behavior.

## 2. Motivation

The current `/gap` page is functional, but its UX still follows the legacy page-form pattern rather than the new workspace pattern.

That creates several issues:

- filters read as a one-shot form rather than a persistent operator control surface,
- the right side of the page is visually under-defined before the first run,
- summary, status, and grouped results feel like separate blocks instead of one coherent work area,
- loading, error, and empty states interrupt the page instead of behaving like states of the result surface,
- the page does not yet align with the SPA design language already emerging on `/comparison` and `/matches`.

A redesign is now lower-risk because:

- SPA cutover is already complete,
- page-local Vue state ownership is already reasonably clean,
- `/gap` can be redesigned mainly in the view layer without a broad backend rewrite.

## 3. Goals

### Primary goals

- Redesign `/gap` into a workspace-style operator page.
- Move the filter model into a persistent left-side control rail.
- Make the right side a clear work surface rather than a loose stack of blocks.
- Add a meaningful pre-run placeholder so the page does not show confusing empty space.
- Keep grouped result presentation by mapped target category.

### Secondary goals

- Improve visual consistency with `/comparison` and `/matches`.
- Keep mutation behavior stable and avoid visible full-page resets.
- Make future compaction and UX polish easier without changing route structure.

## 4. Non-goals

This RFC does **not** include:

- broad redesign of the global SPA shell or sidebar,
- replacing grouped results with a flat global table,
- removing mapped target category selection from the workflow,
- broad backend/API redesign as a prerequisite,
- changing gap business rules or status semantics,
- introducing page-global Pinia ownership for `/gap`.

## 5. Current state

The current page is already inside the SPA, but still behaves visually like a traditional stacked page.

Relevant files include:

- `frontend/src/pages/gap/GapPage.vue`
- `frontend/src/pages/gap/components/GapFilters.vue`
- `frontend/src/pages/gap/components/GapSummary.vue`
- `frontend/src/pages/gap/components/GapStatusBanner.vue`
- `frontend/src/pages/gap/components/GapGroupTable.vue`
- `frontend/src/pages/gap/composables/useGapFilters.ts`
- `frontend/src/pages/gap/composables/useGapData.ts`
- `frontend/src/pages/gap/composables/useGapActions.ts`

Current behavior is already good enough to support a view-level redesign:

- target store is chosen explicitly,
- reference category is chosen explicitly,
- mapped target categories are loaded and explicitly selectable,
- `useGapData.ts` preserves visible data during reloads,
- local patching already exists for status changes where possible.

The redesign should therefore focus on information architecture and layout first.

## 6. Proposed design

## 6.1 Layout model

The page becomes a two-column workspace.

### Left column: Control rail

The left rail contains:

- target store selector,
- reference category selector,
- mapped target categories panel,
- search input,
- availability filter,
- status filters,
- primary action `Показати розрив`.

Design requirements:

- sticky on desktop and wide tablet layouts,
- compact internal grouping,
- visually distinct from the work surface,
- no duplicated primary action outside the rail.

### Right column: Work surface

The right work surface contains:

1. context/header strip,
2. compact KPI row,
3. pre-run placeholder,
4. in-surface loading/error/empty states,
5. grouped result panels.

This surface should always look like a purposeful workspace, even before data has been loaded.

## 6.2 Pre-run placeholder

Before the operator clicks `Показати розрив`, the right work surface must show a meaningful placeholder rather than blank space.

The placeholder should communicate:

- whether a target store is selected,
- whether a reference category is selected,
- whether mapped target categories are available,
- that grouped gap results will appear here after the query runs.

This placeholder is informational, not interactive beyond guiding the operator back to the left rail.

## 6.3 KPI summary

The top of the right work surface should use a **compact KPI strip**, not a large dashboard block.

Preferred metrics include:

- total groups,
- total items,
- available items,
- done / in-progress counts.

The KPI strip supports scanning and context; it should not dominate the page.

## 6.4 In-surface state handling

Loading, error, and empty states should live inside the right work surface, directly below the context/KPI zone.

This means:

- they are treated as states of the result surface,
- they do not float as detached banners between unrelated blocks,
- they do not visually break the workspace structure.

`GapStatusBanner.vue` may remain as a conceptual state component, but should be repositioned/restyled for in-surface ownership.

## 6.5 Grouped results

Grouped results remain grouped by mapped target category.

Each group should render as a compact result panel containing:

- target category header,
- item counts and small metadata,
- compact body rows,
- local empty handling if applicable.

This preserves meaning while making the page easier to scan.

## 6.6 Search and action model

Search remains in the left rail only.

The primary query action also remains in the left rail only.

We intentionally avoid duplicating search or the main run action in the top/right area, so the operator has one stable control zone and one stable result zone.

## 7. State and data model

### State ownership

Existing page-local composables remain the ownership boundary:

- `useGapFilters.ts` owns filter state,
- `useGapData.ts` owns request/result state,
- `useGapActions.ts` owns row/status actions.

The redesign may introduce view helpers, derived display state, or layout-specific computed values, but should not duplicate state across unrelated components.

### Backend/API posture

No broad backend rewrite is required.

The baseline assumption for this RFC is **frontend-first redesign over the current contracts**.

A small additive backend change may be considered separately only if a clearly justified KPI/context improvement cannot be achieved from existing state.

## 8. UX rules

The following behavioral rules apply:

- Left rail is sticky on desktop and wide layouts.
- Mapped target categories remain explicit checkboxes.
- Search lives only in the left rail.
- `Показати розрив` exists only in the left rail.
- Before the first run, the right panel shows a meaningful placeholder.
- Loading/error/empty states live inside the work surface.
- Grouped results stay grouped by mapped target category.
- Row/status mutations should preserve visible context and avoid unnecessary visual resets.

## 9. Rollout strategy

Implementation should follow a staged page-local rollout.

Recommended sequence:

1. introduce workspace shell and placeholder,
2. move summary/status ownership into the right work surface,
3. compact and restyle grouped result panels,
4. harden responsive behavior and tests,
5. sync docs.

This sequence keeps behavior stable while progressively improving the page layout.

## 10. Risks and mitigations

### Risk: left rail becomes too dense

**Mitigation:** visually group controls and keep mapped target categories compact.

### Risk: grouped results become visually noisy

**Mitigation:** use compact group headers and moderate row density rather than adding more container chrome.

### Risk: placeholder and in-surface states conflict with loaded layouts

**Mitigation:** treat all states as variants of the same right-side work surface rather than separate sections.

### Risk: redesign scope expands into shell-level work

**Mitigation:** explicitly keep router, sidebar, and global shell out of scope.

### Risk: behavior regressions during layout changes

**Mitigation:** preserve existing composable ownership and keep behavior-sensitive changes small and staged.

## 11. Acceptance criteria

This RFC is satisfied when:

- `/gap` clearly renders as a workspace page,
- the left rail is sticky on desktop,
- mapped target categories remain explicit and usable,
- the right side shows a meaningful placeholder before the first run,
- KPI, status, and grouped results read as one work surface,
- grouped results remain organized by mapped target category,
- search and main action stay in the left rail only,
- no route or backend regression is introduced,
- tests and docs reflect the new page structure.

## 12. Alternatives considered

### Alternative A: Keep the current stacked page and only polish spacing

Rejected because it would not solve the main problem: `/gap` still would not read as a stable operator workspace.

### Alternative B: Remove mapped target category selection entirely

Rejected because that would change operator behavior and narrow the workflow, not just redesign its presentation.

### Alternative C: Move search into the top/right header

Rejected because it would split control ownership between the filter surface and the result surface.

### Alternative D: Flatten all grouped results into one global table

Rejected because grouping by mapped target category is core to the meaning of the page and should remain visible.
