# ADR-0017: Matches Workspace Redesign

- Status: Accepted
- Date: 2026-03-29
- Supersedes: ADR-0017 draft discussion version
- Related: ADR-0015 Full SPA Transition, ADR-0016 Comparison Workspace Redesign

## Context

The application has already completed the SPA cutover and now uses a shared application shell with page-level Vue modules. The `/matches` page currently works, but its interaction model still reflects an earlier table-first implementation rather than the workspace-oriented operator UI now being adopted across the product.

The operator goal on `/matches` is not generic browsing. The page is used to review confirmed product matches, filter the working set quickly, search by product name, inspect result density, and remove mappings when needed. The current structure does not sufficiently emphasize this workflow.

In parallel, the comparison page is moving toward a workspace layout with a dedicated control rail and a dominant review/result surface. Aligning `/matches` to the same design language will reduce UI drift and make the operator experience more consistent across adjacent workflows.

## Decision

We will redesign `/matches` as a workspace-style page within the existing SPA.

The target layout is:

1. **Left filter rail**
   - Hosts all page filters.
   - Remains the primary place for narrowing the result set.
   - Uses a compact, operator-focused presentation.

2. **Top-center search + KPI zone**
   - Contains the primary name search input.
   - Contains a compact KPI block summarizing the current result set.
   - Lives above the main results panel and below the page title/context.

3. **Main results panel**
   - Remains table-based.
   - Becomes the dominant working surface of the page.
   - Hosts loading, empty, and error states in-place.

## Resolved design defaults

The following defaults are accepted and no longer considered open questions for this redesign cycle.

### Filter rail behavior

- The left filter rail is **sticky on desktop**.
- On narrower screens it collapses into the normal document flow.
- The filter rail remains page-local and does not change the global SPA shell.

### Search behavior

- Search is **explicit**, not debounce-driven live search.
- The search input triggers result loading when the operator submits the query.
- Clear/reset behavior remains predictable and operator-controlled.

### KPI block

The KPI block should summarize the current result set using compact cards or chips, including:
- total rows in scope,
- rows currently visible in the table,
- selected category/store scope,
- any other already-available summary metric that does not require backend redesign.

The KPI block is informational only in this phase.

### Results surface

- The main results surface remains a **table**, not a card grid.
- The table may become more compact, but no broad data-model redesign is part of this ADR.
- Delete/removal actions remain in the results surface.

### State ownership

- `useMatchesPage.ts` remains the single state owner for the page.
- The redesign may split view components, but should not introduce an unnecessary second state layer.
- Pinia is not required unless a real shared state need appears beyond the page boundary.

### Rollout posture

- The redesign is implemented as a **page-local staged refactor**, not a broad shell rewrite.
- The backend API contract is preserved unless a minimal additive change is clearly justified.
- Behavior and route ownership remain inside the SPA.

## Consequences

### Positive

- `/matches` becomes visually and behaviorally aligned with the workspace direction already chosen for `/comparison`.
- Filtering becomes more legible and easier to scan.
- Search becomes a first-class control rather than a secondary utility.
- The results area gains clear visual dominance and better reflects the page's real purpose.
- The page becomes easier to evolve later with no-refresh row updates and table polish.

### Negative

- The redesign introduces additional layout work even though the page is already functional.
- Existing component boundaries may need to shift, especially between filter/search/summary/result responsibilities.
- A temporary mismatch may exist between `/matches` and still-not-redesigned pages until the rest of the UI catches up.

### Neutral / accepted trade-offs

- The redesign does not attempt to solve all table UX issues in one pass.
- No backend rewrite is required as a prerequisite.
- The page remains table-centric even after redesign because that matches the operator use case.

## Out of scope

The following items are explicitly out of scope for this ADR:

- Global SPA shell redesign.
- Router or route-model changes.
- Backend rewrite or broad API redesign.
- Replacing the table with a card-based results UI.
- Cross-page state centralization.
- Comparison-page redesign work.
- Service-page redesign work.

## Implementation notes

Expected implementation will likely touch:

- `frontend/src/pages/matches/MatchesPage.vue`
- `frontend/src/pages/matches/components/MatchesFilters.vue`
- `frontend/src/pages/matches/components/MatchesSummary.vue`
- `frontend/src/pages/matches/components/MatchesTable.vue`
- `frontend/src/pages/matches/components/MatchesTableRow.vue`
- `frontend/src/pages/matches/composables/useMatchesPage.ts`
- related tests under `frontend/src/test/...`

## Validation

The redesign is considered successful when:

- the page clearly presents a left filter rail,
- the search input and KPI block are positioned in the top-center working header,
- the results panel is the dominant visual surface,
- filtering/searching/removal flows still work,
- loading/error/empty states remain clear,
- no backend behavior regression is introduced.
