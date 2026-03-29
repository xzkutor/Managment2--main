# RFC-016 v2: Comparison Workspace Redesign

- Status: Draft
- Owner: Product / Engineering
- Related ADRs:
  - ADR-0015: Full SPA Transition
  - ADR-0016: Comparison Workspace Redesign
- Target area: `frontend/src/pages/comparison/*`

## 1. Summary

This RFC defines the redesign of the SPA comparison page from a long vertical sequence of panels into a compact operator workspace.

The target interaction model is:

- a **left sticky control rail** for page-level controls;
- a **dominant right review workspace** for decision-making;
- a **target store selector** in the left rail;
- **reference category selection only** as the operator-controlled category input;
- no visible reference-store selector;
- no manual target-category selection on the page;
- a **shared right-side drawer** for manual picking instead of inline picker UI inside cards;
- a **compact context strip** in the workspace header where the selected category and target store are clickable.

Compared with the prior draft, this revision fixes four UX decisions:

1. the control-rail category list must show **plain selectable names only** with no URL subtitle and no external link presentation;
2. the context strip must contain **clickable category/store items** that lead to the category/store destination;
3. the sections **Auto Suggestions**, **Needs Manual Choice**, and **Reference Only** must be **collapsible and collapsed by default**;
4. candidate-group and auto-suggestion actions must move to a **compact icon-first design** with tooltip labels.

The redesign remains frontend-first. It must not require a backend rewrite as a prerequisite.

## 2. Motivation

The current comparison page is functional but still inefficient as an operator workspace.

Observed issues in the current SPA implementation:

- the page still reads as a long stack of independent blocks;
- the control area exposes more information than the operator needs at once;
- category items currently surface URL-style presentation that adds noise inside the left rail;
- important review sections always render expanded, increasing page height and scan cost;
- candidate-group cards are visually too tall because manual-pick affordances sit below the reference row;
- confirm/reject actions are text-heavy and visually larger than needed;
- the best navigation affordance for store/category destinations is missing from the result header context area.

The redesign should improve scan speed, reduce page height, and make the operator flow feel deliberate and compact.

## 3. Goals

### 3.1 Primary goals

- Convert the comparison page into a compact operator workspace.
- Reduce page height and visual fragmentation.
- Make decision actions visually lighter but faster to use.
- Keep the left rail focused on control inputs, not navigation links.
- Keep navigation-to-source links available in the workspace context strip.

### 3.2 UX goals

- The operator chooses the **target store**.
- The operator chooses the **reference category**.
- The operator does **not** choose target categories manually.
- The left control rail category list shows **plain selectable names only**.
- The selected category and selected target store are shown in a compact **clickable context strip**.
- Auto suggestions, candidate groups, and reference-only items are each **collapsible** and **collapsed by default**.
- Manual picking opens in one shared drawer from the right side.
- Candidate-group cards are compact, with **manual pick** in the reference row, aligned right.
- Confirm/reject actions use **compact icon-only buttons** with tooltip labels.

### 3.3 Non-goals

This RFC does **not** include:

- redesign of the global SPA shell or sidebar navigation;
- backend comparison logic changes;
- broad API redesign across the project;
- a move away from the current SPA architecture;
- redesign of `/service`, `/gap`, or `/matches`;
- large visual rebranding across unrelated pages.

## 4. Current state

Relevant files in the current SPA implementation include:

- `frontend/src/pages/comparison/ComparisonPage.vue`
- `frontend/src/pages/comparison/components/ComparisonFilters.vue`
- `frontend/src/pages/comparison/components/ComparisonSummaryBar.vue`
- `frontend/src/pages/comparison/components/ReferenceCategoryList.vue`
- `frontend/src/pages/comparison/components/MappedTargetCategoryList.vue`
- `frontend/src/pages/comparison/components/AutoSuggestionsTable.vue`
- `frontend/src/pages/comparison/components/CandidateGroups.vue`
- `frontend/src/pages/comparison/components/CandidateGroupCard.vue`
- `frontend/src/pages/comparison/components/ReferenceOnlySection.vue`
- `frontend/src/pages/comparison/components/TargetOnlySection.vue`
- `frontend/src/pages/comparison/components/ManualPicker.vue`
- `frontend/src/pages/comparison/composables/useComparisonPage.ts`
- `frontend/src/pages/comparison/composables/useManualPicker.ts`
- `frontend/src/pages/comparison/types.ts`
- `frontend/src/types/store.ts`
- `static/css/common.css`

Repo-specific baseline facts to preserve:

- reference store is effectively backend-defined and should not be operator-selectable;
- target store is operator-selectable;
- the operator selects only the reference category;
- target categories are derived from mappings and should not be manually toggled on the page;
- `StoreSummary.base_url` and `CategorySummary.url` already exist and are sufficient for the clickable context strip in most cases.

## 5. Target design

### 5.1 Left sticky control rail

The left rail is a page-level control surface.

It contains:

- target store selector;
- reference category selection;
- compare trigger;
- compact compare status where useful.

It explicitly does **not** contain:

- reference-store selector;
- target-category selector;
- external-link styling for category entries;
- category URL subtitles.

Reference category items remain selectable controls, but not navigation links.

### 5.2 Workspace header

The right workspace begins with a compact results header composed of:

- KPI cards;
- a compact `cw-context-strip`;
- loading / error / compare status where relevant.

The context strip shows the active reference category and target store.

Rules:

- the **category name** is clickable and leads to the selected category URL when available;
- the **store name** is clickable and leads to the target store base URL when available;
- when a destination is missing, the chip falls back to non-clickable text without breaking layout.

### 5.3 Review sections

The main review area is composed of three primary sections:

- **Auto Suggestions**
- **Needs Manual Choice**
- **Reference Only**

Each section must be:

- collapsible;
- collapsed by default after compare results load;
- visually consistent with the same compact section-shell language.

`TargetOnlySection` remains secondary and may stay below the main review surface.

### 5.4 Candidate-group card design

Candidate-group cards should become more compact.

Required layout rules:

- the reference-product row is the card header;
- the **Manual Pick** trigger sits in the same row, aligned right;
- candidate rows remain below the header;
- unnecessary vertical padding is reduced.

The goal is to reduce visual height without losing product context.

### 5.5 Action buttons

Confirm/reject actions for auto suggestions and candidate rows become icon-first.

Required behavior:

- confirm button: green visual treatment;
- reject button: red visual treatment;
- buttons are compact, icon-only in their default visible state;
- human-readable text moves into tooltip / title / accessible label;
- pending state remains visible without expanding button width excessively.

### 5.6 Manual picker behavior

The manual picker is a **shared right-side drawer**.

Required behavior:

- one drawer instance per page;
- opens from the right;
- launched from candidate-group cards and reference-only items;
- shows reference product context in the drawer header;
- confirming a selection patches visible page state locally.

Inline embedded manual-picker UI is not a target-state pattern.

## 6. Functional decisions

The following decisions are fixed by this RFC:

- visible **target store selector** remains;
- visible **reference store selector** is removed;
- the operator chooses only **reference category**;
- target categories are not manually selected on the page;
- left-rail category entries are **plain selectable items**, not navigation links;
- `cw-context-strip` contains the clickable category/store destinations;
- Auto Suggestions, Needs Manual Choice, and Reference Only are collapsible and collapsed by default;
- manual picking uses one shared right-side drawer;
- confirm/reject actions use compact icon-first controls with tooltip labels.

## 7. Technical approach

### 7.1 Frontend-first implementation

This redesign should be implemented primarily inside the comparison page module.

Expected areas of change:

- `ComparisonPage.vue` layout orchestration;
- control-rail and workspace-header composition;
- section-collapse ownership;
- candidate-group card layout;
- action-button treatment;
- manual-picker drawer ownership.

### 7.2 Likely component direction

A likely shape is:

- `ComparisonControlRail.vue`
- `ComparisonSummaryCards.vue`
- `ComparisonContextStrip.vue`
- `ComparisonCollapsibleSection.vue`
- `ComparisonManualPickerDrawer.vue`

Naming may differ, but the ownership split should be similarly clear.

### 7.3 State direction

Preferred approach:

- keep state local to the comparison page module;
- use page composables and small helpers instead of introducing new global state;
- track section collapsed/expanded state locally;
- reuse existing patching helpers for no-refresh decision flows.

## 8. Contract implications

This redesign should avoid backend changes where possible.

Expected contract usage:

- `StoreSummary.base_url` can support clickable target-store chips;
- `CategorySummary.url` can support clickable category chips;
- comparison-result item/product links remain unchanged;
- any missing URL edge case should be handled gracefully in UI first.

Small additive backend changes are acceptable only if the current DTOs prove insufficient during implementation.

## 9. Rollout strategy

Recommended implementation order:

1. prepare page-level shell split and context data;
2. redesign the left control rail and workspace header;
3. add collapsible-by-default review-section shells;
4. compact candidate-group cards;
5. convert confirm/reject actions to icon-first controls;
6. move to a shared right-side manual-picker drawer;
7. finish polish, tests, and docs.

## 10. Risks and mitigations

### Risk: too many changes land at once

Mitigation:
- keep layout, card, action, and drawer changes in separate commits.

### Risk: clickable context strip depends on missing URLs

Mitigation:
- use existing `base_url` / `url` fields first;
- render plain text chips when a link is unavailable.

### Risk: collapsed-by-default sections hide too much

Mitigation:
- show strong counts in KPI cards and section headers;
- keep expand/collapse affordances obvious.

### Risk: icon-only buttons reduce clarity

Mitigation:
- provide `title`, `aria-label`, and consistent green/red semantics;
- preserve visible pending state.

## 11. Acceptance criteria

The redesign is complete when:

- the left rail shows target-store selector, reference categories, and compare control only;
- reference categories are selectable plain items without external-link presentation;
- the workspace header includes clickable category/store context items;
- Auto Suggestions, Needs Manual Choice, and Reference Only are collapsed by default;
- candidate-group cards are visibly more compact;
- manual-pick trigger sits in the candidate-card header row, aligned right;
- confirm/reject buttons are icon-first, compact, and color-coded;
- manual picking works via one shared drawer;
- the page remains stable after decisions without visible full refresh behavior.

## 12. Out of scope reminder

This RFC does not authorize:

- backend comparison-logic rewrites;
- new global SPA shell work;
- redesign of non-comparison routes;
- broad API redesign;
- unrelated visual cleanup outside the comparison module.
