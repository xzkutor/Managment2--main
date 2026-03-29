# ADR-0016: Comparison Workspace Redesign

- Status: **Implemented**
- Date: 2026-03-29
- Implemented: 2026-03-29
- Supersedes: none
- Related: ADR-0015 Full SPA Transition, RFC-015 Full SPA Transition

## Context

The application already runs as a single Vue SPA with a shared shell and page-level routes. The comparison page is the primary operator-facing workflow for reviewing suggested product matches, resolving ambiguous candidates, and handling unmatched reference products.

The current comparison page is functional but still behaves like a vertically stacked sequence of independent blocks:

- filters and selectors at the top;
- summary below them;
- separate sections for auto-suggestions, candidate groups, reference-only products, and target-only products;
- inline manual-pick controls embedded into result cards.

This creates several UX issues:

- the page is too tall and fragmented;
- the main operator workflow is visually diluted across multiple sections;
- manual resolution expands cards vertically and adds noise;
- secondary information competes visually with primary decision-making tasks.

The redesign should turn the comparison page into a focused operator workspace without requiring a backend/API rewrite.

## Decision

We will redesign the comparison page as a two-region operator workspace:

1. **Left sticky control rail**
2. **Right dominant review workspace**

### Left sticky control rail

The left rail will contain only controls that are truly operator-driven for this workflow:

- target store selector;
- reference category selection;
- compare action;
- compact compare status / metadata.

The left rail will **not** include:

- a reference store selector, because the reference store is fixed by backend policy and is not operator-selectable;
- target category selectors, because target categories are derived from mapping rules and are not chosen manually on this page.

### Right dominant review workspace

The right side becomes the main work surface and contains:

- compact KPI / summary cards;
- a unified review flow surface for:
  - auto suggestions,
  - ambiguous candidate groups,
  - reference-only items requiring manual resolution;
- a secondary `target-only` section with reduced visual priority.

### Manual picker interaction model

Manual matching will use a **shared right-side drawer**:

- one drawer instance per page;
- opened from review cards when manual resolution is needed;
- not embedded inline inside result cards;
- shows the reference product context, search, shortlist, and confirm action;
- closes after resolution while the page updates locally without full-page-like refresh behavior.

### Secondary target-only section

`TargetOnlySection` remains part of the page but is explicitly secondary:

- lower visual priority than the main review workflow;
- compact presentation;
- may be collapsed by default if validation confirms that this improves usability.

## Consequences

### Positive

- the comparison page becomes a true operator workspace rather than a stacked report-like view;
- the primary decision flow gains clearer visual priority;
- manual matching becomes more consistent and less noisy;
- the layout better supports future no-refresh interaction hardening.

### Negative / trade-offs

- the redesign requires non-trivial component restructuring in the comparison page module;
- shared drawer ownership introduces new page-level UI state;
- some existing components may need to be merged, replaced, or reduced in responsibility.

## Scope boundaries

Included in scope:

- comparison page information architecture redesign;
- layout redesign;
- unified review workflow presentation;
- shared manual picker drawer;
- visual reprioritization of target-only content;
- local no-refresh behavior where naturally required by the redesigned workflow.

Explicitly out of scope:

- backend/API redesign as a prerequisite;
- changing the fixed reference-store policy;
- exposing manual target-category selection on this page;
- broad shell-level redesign unrelated to the comparison workflow;
- introducing a new UI framework or replacing the existing SPA stack.

## Implementation guidance

The redesign should be implemented incrementally inside the existing comparison page module, centered around:

- `frontend/src/pages/comparison/ComparisonPage.vue`
- `frontend/src/pages/comparison/components/*`
- comparison composables and page-level state shaping

The target end state is:

- fixed reference-store policy reflected in UI;
- target store as the only store selector on the page;
- reference-category-driven compare flow;
- one shared manual picker drawer;
- no inline manual picker inside cards;
- no broad visual reset after operator decisions.

## Validation criteria

The redesign is considered successful when:

- the left rail shows target store, reference-category controls, compare action, and status only;
- the page does not expose a reference selector;
- the page does not expose manual target-category selection;
- manual resolution happens through a shared drawer, not inline card expansion;
- the main review surface visually dominates the page;
- `target-only` information is clearly secondary.

## Implementation record (2026-03-29)

All 9 plan commits implemented. Key file changes:

### New files
- `frontend/src/pages/comparison/components/ComparisonControlRail.vue` — left sticky rail (target store selector, reference category list, compare button)
- `frontend/src/pages/comparison/components/ManualPickerDrawer.vue` — shared right-side drawer for manual product matching
- `frontend/src/pages/comparison/composables/useManualPickerDrawer.ts` — page-level open/close + active ref product state

### Modified: composables
- `patchComparisonResult.ts` — extended `applyDecisionPatch` to remove from `reference_only` and update `summary.reference_only` count
- `useManualPicker.ts` — changed `refProductId` parameter from `number` to `() => number` getter; added `reset()` method
- `useComparisonPage.ts` — added `currentReferenceCategory`, `selectedTargetStore`, `reviewCounts`, `hasReviewContent`, `comparisonWorkspaceState` computed properties

### Modified: components
- `ComparisonPage.vue` — two-column workspace shell; wires rail, KPI bar, review sections, single shared drawer
- `ComparisonSummaryBar.vue` — replaced one-line text summary with KPI cards + context strip
- `AutoSuggestionsTable.vue` — uses `cw-section` + `cw-suggestion-row` layout
- `CandidateGroupCard.vue` — removed inline `ManualPicker`; emits `open-picker`; uses `cw-review-card` layout
- `CandidateGroups.vue` — removed `targetCategoryIds` prop; propagates `open-picker`
- `ReferenceOnlySection.vue` — removed inline `ManualPicker`; emits `open-picker`; uses `cw-section` + `cw-review-card`
- `TargetOnlySection.vue` — demoted to `cw-secondary-section` with collapsed `<details>` by default
- `ManualPicker.vue` — updated to use getter-based `useManualPicker` signature (kept for backward compat, deprecated in practice)

### Modified: CSS
- `static/css/common.css` — added all `.cw-*` workspace classes (rail, KPI grid, review cards, drawer, pick button)
- `static/css/index.css` — removed dead old-layout classes; retained only `.category-item`, `.mapped-target-item`, `.score-pill`, `.btn-reject`, `.picker-search`

### Tests
- `patchComparisonResult.test.ts` — added `reference_only` patching tests; updated untouched-sections tests to reflect new `reference_only` removal behavior
- `ComparisonPage.test.ts` — updated `ComparisonSummaryBar` tests for KPI card layout; updated `useManualPicker` tests for getter signature; added RFC-016 test suites for `ComparisonControlRail`, `ManualPickerDrawer`, `TargetOnlySection`, workspace view-model properties, and `reference_only` removal flow


