# ADR-0014: Incremental Vue 3 Adoption over Flask Templates

- **Status:** Accepted — Superseded for target frontend architecture by [ADR-0015](0015-full-spa-transition.md)
- **Date:** 2026-03-28
- **Decision Makers:** Project maintainers
- **Related:** ADR-0009 UI Polish and Structured Visual Fields for Scheduler Configuration, ADR-0010 Production Runtime Topology: Web + Scheduler + Workers, ADR-0012 Product Match Review Workflow, ADR-0013 HTTP Page Cache TTL Configuration, RFC-010 UI Polish and Structured Visual Fields

## Context

The repository is currently a Flask application with server-rendered HTML pages and page-specific JavaScript.

Current UI entry points are:

- `templates/index.html`
- `templates/service.html`
- `templates/gap.html`
- `templates/matches.html`
- `static/js/index.js`
- `static/js/service.js`
- `static/js/service.*.js`
- `static/js/gap.js`
- `static/js/matches.js`
- `static/css/common.css`
- `static/css/*.css`

The current frontend model is functional, but it has the following limitations:

1. complex operator screens rely on imperative DOM manipulation;
2. reusable UI primitives are limited;
3. styling consistency requires repeated manual work across pages;
4. stateful flows such as scheduler/job/schedule management are becoming harder to evolve safely;
5. the project needs a stronger component model without destabilizing the existing Flask application shell.

At the same time, the current repository does **not** need a full frontend-platform replacement.

The Flask application already owns:

- route composition;
- template rendering;
- application config injection;
- operational/admin page boundaries;
- existing `/api/...` endpoints;
- current production deployment model.

The goal is therefore to improve frontend maintainability and UX while preserving the repository's current backend-first architecture.

## Decision

The project will adopt **Vue 3 + Vite + TypeScript** as the frontend component/runtime layer using an **incremental migration strategy over existing Flask templates**.

## Decision Summary

The approved direction is:

- adopt Vue 3 as the interactive UI framework;
- adopt Vite as the frontend build and development toolchain;
- adopt TypeScript for new frontend code;
- keep Flask as the owner of routes, templates, and backend API contracts;
- migrate the frontend page-by-page and panel-by-panel rather than through a full SPA rewrite;
- begin with the Service Console scheduler area as the first Vue migration target;
- delay migration of the main comparison page until shared Vue primitives and integration patterns are stable.

## Decision Drivers

- Improve maintainability of stateful admin/operator UI.
- Establish reusable UI primitives and a more coherent design language.
- Reduce imperative DOM wiring in complex screens.
- Preserve existing Flask routing, template ownership, and deployment shape.
- Minimize migration risk by keeping scope incremental.
- Avoid coupling frontend modernization to unrelated runtime/backend changes.

## Architectural Rules

### 1. Flask remains the application shell

Flask continues to own:

- route registration and URL structure;
- server-rendered page entry points;
- config/environment injection into templates;
- existing backend service/API orchestration.

This ADR does **not** authorize replacing Flask with a frontend-first application shell.

### 2. Vue is adopted incrementally, not as a big-bang rewrite

Vue components may be mounted into existing pages using dedicated mount roots inside Jinja-rendered templates.

The migration must proceed page-by-page or panel-by-panel.

The project must not switch all pages to a full SPA in the first wave.

### 3. Vite is the build boundary for new frontend code

New frontend code will live under a dedicated frontend workspace, expected to be introduced as:

- `frontend/`
  - `src/`
  - `entries/`
  - `components/`
  - `composables/`
  - `api/`
  - `types/`
  - `styles/`

Production assets will be built into `static/dist/`, with manifest-based asset lookup from Flask.

### 4. TypeScript is the default for all new Vue/frontend modules

New Vue components, composables, API wrappers, and page entry files should use TypeScript.

The initial TypeScript posture is pragmatic rather than maximally strict. Strictness may be tightened after the first migrated page stabilizes.

Existing legacy JavaScript may remain temporarily where migration has not started yet.

### 5. Existing API contracts remain the primary backend boundary

The Vue rollout must initially reuse the current backend route and JSON contract surface.

The migration must not depend on a broad backend API redesign in the first wave.

Where API inconsistencies are discovered, they should be handled through a thin frontend API adapter layer first, unless a separate ADR/RFC approves contract changes.

### 6. Shared UI primitives must be established before broad page migration

Before migrating many pages, the repository should define a small shared frontend primitive layer, for example:

- buttons;
- dialog shell;
- status pills;
- panel/card containers;
- data table shell;
- empty states;
- common async state/loading/error patterns.

This is required to avoid creating a second generation of inconsistent controls.

### 7. CSS ownership remains incremental and conservative

The project will keep `static/css/common.css` as the shared visual base in the first migration wave.

Vue areas may introduce component-local styles where helpful, but the project should avoid introducing a full CSS framework in the first wave.

The initial direction is to evolve toward reusable primitives and lightweight tokens/utilities rather than wholesale CSS replacement.

### 8. The first migration target is the Service Console scheduler area

The first Vue implementation target should be the scheduler panel within `templates/service.html`.

Reasons:

- it is already the most stateful admin UI area;
- it already has partial JS modularization;
- it benefits immediately from componentization;
- it has lower architectural risk than rewriting the main comparison workflow first.

The first scheduler wave should prioritize read-only flows, selection/detail rendering, and recent run refresh. Mutating flows should follow in the next commit wave.

### 9. The main comparison page is deferred

The main comparison page should migrate only after:

- the Flask/Vite integration pattern is stable;
- shared components exist;
- at least one Service Console section is successfully migrated;
- the repo has a settled pattern for Vue-driven data loading and modal/action flows.

It remains intentionally last in the migration order unless a separate reprioritization decision is made.

### 10. Legacy JS must be retired per migrated area

For each migrated page or panel, ownership should become explicit.

The repository should avoid long-term dual ownership where both legacy imperative JS and Vue manage the same DOM subtree.

Temporary overlap is acceptable only during a short controlled migration step.

### 11. Frontend runtime additions stay minimal in the first wave

The project will not introduce Nuxt, Vue Router, Pinia, or a third-party UI kit in the first migration wave.

These may be reconsidered later only if actual repository needs emerge.

### 12. Operator-facing UI text follows the existing page language

New frontend UI text should follow the existing operator-facing language of the migrated page.

The project will not introduce full i18n infrastructure in the first wave.

## Resolved Implementation Defaults

The following implementation defaults are approved for the first rollout wave:

### Flask ↔ Vite integration

- add a small Flask asset helper under `pricewatch/web/assets.py` or equivalent web-layer helper module;
- use Vite manifest lookup in production;
- use the Vite dev server only in local development.

### Initial data loading model

- prefer API fetch after mount for page data;
- allow only minimal inline bootstrap for stable metadata, config flags, and mount-time constants.

### Frontend test minimum

- use `Vitest` + `Vue Test Utils` for component and composable tests;
- add one smoke E2E path for the first migrated scheduler workflow.

### Migration fallback policy

- do not introduce a heavy feature-flag framework for the Vue rollout;
- use short-lived fallback only where migration risk is unusually high.

## Consequences

### Positive

- Better structure for complex operator workflows.
- Easier UI evolution and testing.
- Stronger path toward consistent design primitives.
- Lower long-term maintenance cost for state-heavy screens.
- Reduced risk versus a full rewrite.
- Better fit with the existing Flask architecture.

### Negative

- Build/dev tooling becomes more complex because Node/Vite is introduced.
- The repository temporarily carries both legacy JS and the new Vue layer.
- Frontend testing/tooling standards must be maintained.
- The team must preserve a clear boundary between migrated and non-migrated pages.

## Rejected Options

### Option A — Keep improving vanilla JS only

Rejected.

This preserves the current runtime shape but does not solve the componentization and maintainability problem for increasingly stateful admin UI.

### Option B — Rewrite the whole frontend as a full SPA immediately

Rejected.

This would create unnecessary migration risk, increase blast radius, and force routing/application-shell changes that the current project does not need.

### Option C — Introduce Nuxt or another frontend-first application shell

Rejected for now.

This would duplicate concerns already handled by Flask and would be disproportionate to the current repository needs.

### Option D — Adopt React first

Rejected for this repository.

React is viable technically, but Vue fits the current server-rendered page model and incremental mounting strategy more naturally for this codebase.

## Initial Migration Order

The expected migration order is:

1. ADR acceptance and implementation defaults;
2. frontend workspace scaffold (`frontend/`, Vite, TypeScript);
3. Flask/Vite asset integration and manifest loading;
4. shared frontend primitives and API client layer;
5. Service Console scheduler tab — read-oriented flows;
6. Service Console scheduler tab — mutating flows;
7. Service Console mappings tab;
8. Service Console history tab;
9. Service Console categories tab;
10. `matches` page;
11. `gap` page;
12. main comparison page.

## Acceptance Criteria

This ADR is considered satisfied when:

- the repository has an approved Vue/Vite integration model;
- Flask continues to serve application pages successfully;
- production assets can be built and served through Flask;
- at least one real Service Console area is fully migrated to Vue;
- the migrated area no longer depends on legacy JS ownership for its main interactive flow.

## Non-Goals

This ADR does not authorize:

- replacing Flask routing with a SPA router across the application;
- introducing Nuxt as the primary application shell;
- rewriting all backend API contracts in the same change wave;
- replacing the current visual system with a new CSS framework in the first wave.
