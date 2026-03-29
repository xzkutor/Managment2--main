# RFC-017: Matches Workspace Redesign

- Status: Draft
- Date: 2026-03-29
- Owner: Product/UI implementation track
- Related: ADR-0015 Full SPA Transition, ADR-0016 Comparison Workspace Redesign, ADR-0017 Matches Workspace Redesign

## 1. Summary

This RFC proposes a workspace-style redesign of the `/matches` page inside the existing Vue SPA.

The redesign introduces:

- a **left sticky filter rail**,
- a **top-center search and KPI header zone**,
- a **dominant results panel** for confirmed match rows.

The goal is to align `/matches` with the operator-oriented workspace model already being adopted elsewhere in the application, while preserving current page ownership, route behavior, and backend contracts.

## 2. Motivation

The current `/matches` page is functional but visually closer to a traditional admin list than to a focused operator workspace. That creates several issues:

- filters do not feel like a persistent working control area,
- search does not have enough visual priority,
- summary information is not strongly separated from the results surface,
- the page does not yet align with the emerging workspace language used for comparison and other operator-heavy flows.

A redesign now is lower-risk than waiting, because:

- the SPA cutover is already complete,
- `/matches` is page-local and structurally simpler than `/comparison`,
- the page already has a clear state owner and a stable route.

## 3. Goals

### Primary goals

- Redesign `/matches` into a workspace-style operator page.
- Move all filters into a persistent left-side rail.
- Promote name search into the top working header.
- Add a compact KPI block above the results panel.
- Keep the results table as the dominant working surface.

### Secondary goals

- Improve visual consistency with the comparison workspace direction.
- Make later no-refresh interaction improvements easier.
- Preserve current route and API behavior.

## 4. Non-goals

This RFC does **not** include:

- changing global SPA shell navigation,
- redesigning `/comparison`, `/service`, or other pages,
- replacing the results table with cards,
- broad backend/API redesign,
- introducing Pinia-based global state for `/matches`,
- changing canonical route ownership.

## 5. Current state

The current page is built inside the SPA and is centered around page-local Vue components and a page-level composable.

Relevant files include:

- `frontend/src/pages/matches/MatchesPage.vue`
- `frontend/src/pages/matches/components/MatchesFilters.vue`
- `frontend/src/pages/matches/components/MatchesSummary.vue`
- `frontend/src/pages/matches/components/MatchesTable.vue`
- `frontend/src/pages/matches/components/MatchesTableRow.vue`
- `frontend/src/pages/matches/composables/useMatchesPage.ts`

The page already supports filtering, loading results, and removing mappings. The redesign focuses on information architecture and layout rather than route or backend behavior.

## 6. Proposed design

## 6.1 Layout model

The page becomes a two-column workspace with an upper working header in the main content area.

### Left column: Filter rail

The left column contains:

- store/category scope filters,
- any existing page filters already supported by the page,
- reset/apply controls if needed by the current page flow.

Design requirements:

- sticky on desktop,
- compact spacing,
- visually distinct from the results area,
- no duplication of search controls here.

### Main column: Working header + results panel

The main column contains:

1. page heading/context,
2. top-center search input,
3. KPI summary block,
4. dominant results panel.

The search and KPI zone should appear before the results table and should read as one working header.

## 6.2 Search behavior

Search is explicit.

- The operator types a query.
- The operator submits the search.
- The page updates the result set.

We intentionally avoid debounce/live search in this redesign phase because the operator workflow benefits from explicitness and predictability.

## 6.3 KPI block

The KPI block should present compact, high-signal summary items derived from already available page state.

Preferred metrics:

- total result count,
- visible/loaded rows,
- current scope summary,
- any existing table-relevant metric already computed by the page.

The KPI block is not interactive in this phase.

## 6.4 Results panel

The results area remains table-based.

Requirements:

- strong visual prominence,
- clean handling of loading/error/empty states,
- compact but readable row density,
- row actions remain clear.

Removal of mappings remains available within the results surface.

## 7. State and data model

### State ownership

`useMatchesPage.ts` remains the single state owner.

The redesign may introduce derived view helpers or split presentational components, but should not introduce unnecessary duplicated state.

### Backend/API posture

No backend rewrite is required.

If a minimal additive API change becomes clearly beneficial for better KPI presentation, it may be considered separately, but the default assumption for this RFC is **frontend-only redesign over existing contracts**.

## 8. UX rules

The following behavioral rules apply:

- The filter rail is sticky on desktop.
- Search is explicit.
- The results panel is the dominant visual surface.
- Loading/error/empty states live inside the working area, not as detached banners.
- The redesign should not introduce browser-level reload behavior.
- Delete/removal flow must remain clear and safe.

## 9. Rollout strategy

Implementation should follow a staged page-local rollout.

Recommended sequence:

1. prepare state/view helpers if needed,
2. split the page into workspace layout regions,
3. move filters into the left rail,
4. move search + KPI into the working header,
5. reshape the results panel/table presentation,
6. update tests and docs.

This sequence reduces risk by separating layout restructuring from behavior-sensitive result operations.

## 10. Risks and mitigations

### Risk: layout churn breaks table behavior

**Mitigation:** keep `useMatchesPage.ts` as the single state owner and avoid behavior changes during initial layout commits.

### Risk: sticky filter rail behaves poorly on narrow screens

**Mitigation:** desktop sticky only; collapse to normal flow on smaller breakpoints.

### Risk: search/KPI area becomes visually noisy

**Mitigation:** keep KPI block compact and informational; preserve the table as the dominant results surface.

### Risk: redesign scope expands into shell-level work

**Mitigation:** explicitly keep shell/router/global SPA layout out of scope.

## 11. Acceptance criteria

This RFC is satisfied when:

- `/matches` clearly renders as a workspace page,
- filters are presented in a left sticky rail on desktop,
- search and KPI appear in the upper center of the main working area,
- results remain table-based and visually dominant,
- current filter/search/remove flows still work,
- no route or backend regression is introduced,
- tests and docs reflect the new page structure.

## 12. Alternatives considered

### Alternative A: Keep the current table-first page with minor polish

Rejected because it would not align `/matches` with the workspace direction already chosen elsewhere.

### Alternative B: Put search into the left rail with the rest of the filters

Rejected because search is a primary working action and should stay visually close to the results surface.

### Alternative C: Replace the results table with cards

Rejected because `/matches` is best served by compact, scannable tabular review.
