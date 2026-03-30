# ADR-0019: Service Console Redesign

- Status: Accepted
- Date: 2026-03-30
- Implemented: 2026-03-30
- Owners: UI / Frontend
- Supersedes: none
- Related: ADR-0015 (full SPA transition), ADR-0016 (comparison workspace redesign), ADR-0017 (matches workspace redesign), ADR-0018 (gap workspace redesign)

## Context

The `/service` page is now the most legacy-shaped SPA surface in the application UI.

While `/comparison`, `/matches`, and `/gap` have already moved toward workspace-style layouts, `/service` still behaves like a tabbed admin console carried over from the old multi-page UI:

- top tab bar in `frontend/src/pages/service/ServicePage.vue`
- all sections mounted eagerly via `v-show`
- each section visually optimized as a self-contained island, not as part of one coherent console
- inconsistent page rhythm across `categories`, `mappings`, `scheduler`, and `history`
- weak page-level hierarchy: the user first sees tabs, then independent blocks, rather than one service operations workspace

This is especially visible in the current component structure:

- `ServicePage.vue` owns top tabs only
- `ServiceCategoriesTab.vue` still reads like a legacy sync/admin surface
- `MappingsTab.vue` is a toolbar + table flow
- `SchedulerApp.vue` is already a two-column workspace
- `ServiceHistoryApp.vue` is still closer to a filtered table

The result is functionally correct but visually fragmented.

## Decision

We will redesign `/service` as a **service operations console** with a unified workspace structure instead of a legacy top-tab page.

### Target UX model

`/service` becomes a page with:

1. **Local left section rail** inside the page
   - Categories
   - Mappings
   - Scheduler
   - History
   - optional counts / status badges where useful

2. **Right main workspace area**
   - context/header for the active section
   - section-specific toolbar or KPI strip where needed
   - one dominant work surface for the active section
   - in-surface loading / empty / error states

3. **Section-specific layouts** aligned to the newer workspace language
   - Categories: **single workspace**, not a dual-pane screen
   - Mappings: filter/action rail + results workspace
   - Scheduler: keep two-column structure but align visuals and chrome
   - History: filter rail + run history workspace

### Categories-specific decision

The Categories section will **not** remain dual-pane.

Reasoning:
- the left and right sides currently expose largely symmetrical logic
- keeping two panes suggests a meaningful asymmetry that the workflow does not actually have
- the split consumes too much horizontal space without adding practical operator value
- on a redesigned service console, Categories should read as one coherent operational surface, not two competing mini-panels

Target direction for Categories:
- one section header
- one compact control area
- one primary results/work surface
- reference/target context may still be visible where needed, but not as two permanent peer panes

### Structural direction

The redesign target is **not** “make the tab bar prettier”.
The redesign target is to replace the top-tab mental model with a console-style layout that matches the rest of the SPA.

### Scope boundaries

Included:
- `/service` layout, navigation model, section chrome, and visual hierarchy
- service-specific UX alignment across categories / mappings / scheduler / history
- better empty / loading / status surfaces
- reducing the feeling that `/service` is four unrelated mini-apps

Not included by default:
- backend rewrite
- scheduler domain/model rewrite
- changes to queue semantics or worker runtime
- changes to `/comparison`, `/matches`, `/gap`
- broad API redesign as a prerequisite

## Consequences

### Positive

- `/service` will visually align with the rest of the redesigned SPA
- the page will read as one service operations area instead of a collection of tabs
- clearer hierarchy improves discoverability of scheduler/history/admin actions
- future UX work becomes easier because each section will live inside the same page-level frame
- Categories will stop wasting horizontal space on an artificial two-pane split

### Costs / Risks

- the page is structurally more complex than `/comparison` or `/matches`
- there is a design choice to make between keeping local tabs vs introducing nested service routes
- some existing eager-mount behavior may need to change if we move away from `v-show`
- service page state preservation across section switches must be handled intentionally
- Categories redesign now requires a more deliberate rethink than a simple chrome refresh

## Recommended baseline for follow-up RFC

The RFC should assume the following as the default starting position:

- `/service` should gain a **local left section rail**
- the **top tab bar should not remain the target design**
- the active section should occupy the right-hand workspace
- each section should move toward workspace-style internals
- **Categories should be redesigned as a single workspace, not a dual-pane surface**
- section loading/empty/error states should live inside the active workspace
- redesign should remain frontend-first and avoid backend rewrite as a prerequisite

The RFC should also explicitly resolve whether `/service` remains a single route with local section state, or becomes route-addressable via nested SPA routes.

## Implementation Summary

Implemented as a 9-commit incremental rollout (service-console-redesign-copilot-plan-v2):

| Commit | Scope |
|--------|-------|
| 01 | Service shell routing — `ServiceRouteView.vue` left rail + `RouterView`; child routes `/service/*` |
| 02 | Categories redesigned as single workspace with top-centred target-store control panel |
| 03 | `useServiceContext.ts` — shared current target store across service sections |
| 04 | Mappings create/edit replaced with right-side `MappingDrawer.vue` (replaces modal) |
| 05 | Drawer form simplified to 3 fields only (ref-category, target-store, target-category) |
| 06 | Mappings workspace polish: inner rail + dominant results table |
| 07 | History filters moved to top horizontal bar; no left-rail filter layout |
| 08 | Scheduler visual alignment with service console chrome |
| 09 | Tests (36 new assertions), docs updated, `ServicePage.vue` old tab code removed |

All acceptance criteria from RFC-019 are met:
- `/service` no longer uses the top-tab primary navigation model.
- Service sections are reachable through canonical subroutes.
- `Categories` uses a single-workspace layout (no dual-pane).
- `Mappings` uses a right-side drawer for create/edit.
- `History` uses a horizontal top filter bar.
- `Scheduler` is visually aligned with the service console.
- Inactive sections are **not** simultaneously mounted (route-driven, no `v-show`).

