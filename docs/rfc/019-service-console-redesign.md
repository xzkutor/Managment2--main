# RFC-019: Service Console Redesign

- Status: Proposed
- Date: 2026-03-30
- Related ADR: ADR-0019 Service Console Redesign (v2)
- Related scope: `/service` SPA route and service submodules only

## Summary

Redesign `/service` from a legacy tab-style admin page into a route-addressable, workspace-style service console with a local left section rail and a dominant right-side work area.

This RFC replaces the current top-tab interaction model in `frontend/src/pages/service/ServicePage.vue` with a service-local shell that aligns visually and behaviorally with the already redesigned `/comparison`, `/matches`, and `/gap` pages.

The redesign is frontend-first. Flask, backend API contracts, and the global SPA shell remain intact unless a narrowly scoped UI-supporting change is required.

## Motivation

The current `/service` page is technically inside the SPA, but UX still reflects the earlier tabbed admin-console model:

- `ServicePage.vue` renders a top tab bar.
- All major sections are mounted at once and toggled with `v-show`.
- `categories`, `mappings`, `scheduler`, and `history` behave like separate mini-apps placed on one page.
- The page does not read as a single operator-facing workspace.

This creates several practical issues:

1. Weak information hierarchy. The top tab bar provides only coarse navigation and does not give each section a stable local shell.
2. High mount and preload cost. Current `v-show` behavior keeps all sections mounted even when not visible.
3. Inconsistent UX language compared with newer workspace pages.
4. Uneven redesign maturity across sections:
   - `scheduler` is already the closest to a mature operator workflow.
   - `mappings` and `history` still read as tool panels.
   - `categories` still carries a dual-pane structure that no longer reflects actual operator value.

## Goals

1. Convert `/service` into a workspace-style service console.
2. Replace top tabs with a service-local left section rail.
3. Make service sections route-addressable.
4. Reduce unnecessary simultaneous mounting of all service sections.
5. Redesign `categories` as a single dominant workspace, not a dual-pane layout.
6. Bring `mappings` and `history` to the same workspace language used on other redesigned pages.
7. Preserve existing core operator capabilities and backend behavior.

## Non-Goals

This RFC does **not** include:

- broad backend rewrite;
- API redesign across the application;
- changes to the global SPA shell, top-level sidebar, or main router structure outside `/service`;
- redesign of `/comparison`, `/matches`, or `/gap`;
- full scheduler domain redesign.

Scheduler may receive UI polish during implementation, but its core interaction model remains intact unless a later RFC explicitly changes it.

## Current Repo State

The current service UI structure is already modularized and therefore suitable for an incremental frontend redesign:

- `frontend/src/pages/service/ServicePage.vue`
- `frontend/src/pages/service/ServiceRouteView.vue`
- `frontend/src/pages/service/composables/useServiceTabs.ts`
- `frontend/src/pages/service/categories/ServiceCategoriesTab.vue`
- `frontend/src/pages/service/categories/components/*`
- `frontend/src/pages/service/mappings/MappingsTab.vue`
- `frontend/src/pages/service/mappings/components/*`
- `frontend/src/pages/service/scheduler/SchedulerApp.vue`
- `frontend/src/pages/service/scheduler/components/*`
- `frontend/src/pages/service/history/ServiceHistoryApp.vue`
- `frontend/src/pages/service/history/components/*`
- `frontend/src/router/routes.ts`

This modularity makes the redesign feasible without changing the overall SPA architecture.

## Target UX Model

### 1. Service-level layout

`/service` becomes a local workspace page with:

- **left section rail** for switching between service sections;
- **right dominant workspace area** where the selected section renders.

The left rail is local to `/service`; it does not replace the existing global application sidebar.

### 2. Route-addressable service sections

Service sections become explicit subroutes rather than in-page tabs controlled only by local state.

Target shape:

- `/service/categories`
- `/service/mappings`
- `/service/scheduler`
- `/service/history`

`/service` should redirect to a canonical default subroute, recommended: `/service/categories`.

### 3. Section-by-section target model

#### Categories

`Categories` must **not** remain dual-pane.

Reasoning:

- The left and right panes currently expose substantially similar logic.
- The dual-pane layout creates visual duplication without strong operator value.
- The section should instead present one dominant working surface with clear action grouping.

Target behavior:

- one dominant categories workspace;
- one clear store-context selection model;
- scrape-status information integrated into the section header or a compact status strip;
- sync actions surfaced according to role and current context;
- category rows presented in a single, coherent results surface.

#### Mappings

`Mappings` becomes a workspace with:

- a local left rail for filters and store selectors;
- a right results workspace for the mappings table and supporting banners/dialogs;
- reduced visual emphasis on toolbar-style controls;
- clearer empty/loading/error surfaces.

#### Scheduler

`Scheduler` remains fundamentally a two-column operator workflow:

- jobs list / navigation surface;
- detail + schedule + recent runs surface.

The redesign goal is not to replace its interaction model, but to align its shell, density, and visual language with the rest of the service console.

#### History

`History` becomes a clearer workspace with:

- left filter rail;
- right results panel;
- consistent KPI/header/status treatment;
- details dialog behavior that fits the service console rather than a standalone table page.

## Technical Design

### Routing

Add explicit nested routes for `/service/*` under the existing SPA router.

Recommended structure:

- `ServiceRouteView.vue` becomes the local service shell host.
- `ServicePage.vue` is replaced or substantially rewritten to render:
  - service section rail;
  - `<RouterView>` for service child routes.

The existing `useServiceTabs.ts` should be retired or replaced by route-derived state.

### Mounting model

Stop mounting all service sections simultaneously with `v-show`.

Target behavior:

- only the active service section route mounts by default;
- preserve state intentionally only where justified;
- avoid hidden-background mounting as the default model.

If specific subviews need keep-alive behavior later, this should be added explicitly rather than preserved via the old tab strategy.

### Service-local shell

The service console should have its own local shell primitives, likely including:

- service section rail component;
- service page header/context strip;
- common workspace container conventions;
- shared empty/loading/error panel styles that match the redesigned pages.

### Styling

The redesign should continue using the existing SPA styling direction and `static/css/common.css`, but service-specific styles may be extracted into local component styles or scoped service-page classes where that improves maintainability.

No new CSS framework is introduced.

## Data and Backend Considerations

This redesign is frontend-first.

Default rule:

- do not change backend behavior unless a narrowly scoped frontend-supporting issue requires it.

Examples of acceptable backend changes:

- tiny DTO additions required for display clarity;
- route-safe URL helpers or metadata already derivable from existing backend models.

Examples of out-of-scope backend changes:

- service API redesign;
- scheduler behavior rewrite;
- scrape/job execution model changes.

## Rollout Strategy

The redesign should be staged and low-risk.

Recommended sequence:

1. Introduce service-local shell and route model.
2. Migrate section navigation from tab-state to router-state.
3. Redesign `categories` into a single-workspace surface.
4. Redesign `mappings` into rail + workspace.
5. Align `scheduler` shell and visual language.
6. Redesign `history` into rail + workspace.
7. Remove obsolete tab-based code and docs.

## Risks

### 1. Scope sprawl

`/service` covers several distinct operational domains. Without strict commit boundaries, implementation can drift into a broad rewrite.

Mitigation:

- implement section-by-section;
- keep backend changes narrow;
- preserve existing behavior during layout conversion wherever possible.

### 2. State regression

Replacing `v-show` tabs with route-based sections may expose assumptions about persistent in-memory state.

Mitigation:

- define which state should persist and which can reset;
- add route-level tests;
- add smoke coverage for section switching.

### 3. Categories ambiguity

Because `categories` is moving away from a dual-pane layout, there is risk of reintroducing implicit symmetry later.

Mitigation:

- lock in the single-workspace decision in implementation plans;
- explicitly reject mirrored pane designs.

### 4. Visual inconsistency within `/service`

If sections are redesigned independently without shared service-shell conventions, the result may still feel fragmented.

Mitigation:

- create service-local shell primitives first;
- reuse common context/header/rail/result-surface patterns.

## Testing Strategy

At minimum, implementation should add or update tests for:

- `/service` route behavior;
- default redirect to canonical section route;
- section rail active-state behavior;
- section mount behavior when changing routes;
- categories workspace rendering under the new single-panel design;
- mappings/history section rendering and empty/loading states;
- scheduler visual-shell stability;
- regression coverage for service-specific navigation.

Existing frontend tests under `frontend/src/test/...` should be extended rather than bypassed.

## Acceptance Criteria

This RFC is considered implemented when all of the following are true:

1. `/service` no longer uses the old top-tab UI as the primary navigation model.
2. Service sections are reachable through canonical subroutes.
3. `Categories` no longer uses the previous dual-pane layout.
4. `Mappings` renders as a workspace rather than a toolbar-plus-table page.
5. `History` renders as a workspace rather than a stacked filters/table page.
6. `Scheduler` remains operational and visually aligned with the redesigned service console.
7. Hidden simultaneous mounting of all major service sections is removed as the default behavior.
8. Service-related tests and documentation are updated.

## Rollback Posture

Because this redesign is frontend-first, rollback should primarily mean restoring the previous service route rendering and section shell behavior.

To keep rollback cheap:

- do not combine router conversion and all section redesigns in one commit;
- preserve backend API contracts during the redesign;
- avoid mixing service redesign with unrelated SPA shell work.

## Alternatives Considered

### Keep top tabs and only restyle the page

Rejected.

This would preserve the core structural issues:

- weak service-level navigation model;
- simultaneous mounting via `v-show`;
- fragmented section ownership;
- poor alignment with the rest of the redesigned SPA.

### Keep `Categories` dual-pane but improve styling

Rejected.

The dual-pane structure does not provide sufficient practical value because both panes express substantially similar operator logic.

### Split each service section into a top-level global route group

Rejected for now.

This would over-expand global app navigation and blur the boundary between application-level pages and service-local sections.

## Follow-up

After this RFC, the next document should be a strict repo-aware implementation plan commit-by-commit for Copilot, with separate commits for:

- service-local routing/shell introduction;
- categories single-workspace redesign;
- mappings workspace redesign;
- scheduler shell alignment;
- history workspace redesign;
- cleanup/tests/docs.
