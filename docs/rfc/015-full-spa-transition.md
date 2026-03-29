# RFC-015: Full SPA Transition for the Operator UI

- **Status:** Implemented
- **Date:** 2026-03-29
- **Implemented:** 2026-03-29
- **Depends on:** ADR-0015 Full SPA Transition
- **Supersedes (target architecture):** RFC-less hybrid multi-entry Vue-over-Flask end state derived from ADR-0014
- **Related ADRs:** ADR-0009, ADR-0010, ADR-0014, ADR-0015
- **Owners:** Project maintainers

## 1. Summary

This RFC defines the repository-aligned implementation plan for moving the operator-facing frontend from the current **multi-page Vue-over-Flask** model to a **single Vue SPA**.

The repository already contains a substantial Vue/Vite frontend migration:

- a dedicated `frontend/` workspace;
- page-level Vue applications for `/`, `/service`, `/gap`, and `/matches`;
- Flask asset integration via `pricewatch/web/assets.py`;
- thin Jinja template shells under `templates/`.

The next step is to convert this partially consolidated frontend into a canonical **single application / single router / single shell** model while keeping Flask as the backend and API owner.

The target end state is:

- one Vite application entrypoint;
- one Vue root application;
- one Vue Router route tree;
- one shared application shell and navigation model;
- one Flask-served SPA shell template for operator UI routes;
- Flask retained as API/backend owner, not page-shell owner.

## 2. Motivation

The current hybrid state was the correct transitional step, but it is no longer the desired target architecture.

The repository already demonstrates that Vue is the right UI technology direction, but the current shape still carries multi-entry and multi-shell costs:

- separate entry files under `frontend/src/entries/`;
- separate template shells under `templates/index.html`, `templates/service.html`, `templates/gap.html`, and `templates/matches.html`;
- page-local bootstrap assumptions;
- limited shared navigation/state ownership across pages;
- continued Flask ownership of route-level HTML documents.

This creates friction in several areas:

1. **Navigation model drift**
   - each operator page is still a separate HTML shell even though most UI is already Vue;
   - route-to-route transitions still conceptually belong to Flask pages rather than one client application.

2. **State fragmentation**
   - shared state and reference data are harder to centralize when the frontend is split into multiple entrypoints;
   - common caching and invalidation rules become inconsistent.

3. **Build complexity**
   - Vite manifest usage is still tied to multiple operator HTML pages;
   - the application is conceptually one admin UI, but the build still treats it as several smaller apps.

4. **Frontend evolution limits**
   - full-page cross-section flows, route guards, persistent shell state, and app-wide stores are unnatural in the current structure;
   - future UX improvements remain constrained by the multi-page boundary.

The repository is now mature enough to collapse the transitional structure into a proper SPA without starting from zero.

## 3. Goals

This RFC aims to:

1. define the target SPA architecture for operator-facing UI;
2. replace the current multi-entry frontend with a single Vue application entrypoint;
3. introduce Vue Router as the canonical operator navigation model;
4. introduce Pinia for shared client-side state where shared state is genuinely needed;
5. move route-level shell ownership from Jinja page templates into the SPA;
6. standardize operator UI bootstrap/config delivery for the SPA model;
7. define Flask responsibilities in the new model;
8. define the migration path from current hybrid state to full SPA;
9. define test and rollout expectations for the cutover.

## 4. Non-goals

This RFC does not attempt to:

1. replace Flask as the backend or API layer;
2. introduce Nuxt, SSR, or a separate frontend deployment stack;
3. redesign domain workflows such as comparison, gap review, mappings, or scheduler semantics;
4. rewrite backend APIs solely to fit a new frontend framework style;
5. introduce GraphQL, WebSockets, or a client-side offline model;
6. redesign authentication/authorization in this wave;
7. migrate public/non-operator pages to a separate frontend system;
8. perform broad visual redesign beyond what is required for shared SPA shell coherence.

## 5. Current repository state

At the time of this RFC, the repository already contains the following frontend building blocks:

### 5.1 Existing Vue/Vite foundation

- `frontend/` workspace with Vue 3, Vite, TypeScript, and tests;
- reusable base components under `frontend/src/components/base/`;
- shared API helpers under `frontend/src/api/`;
- page implementations under `frontend/src/pages/`.

### 5.2 Existing multi-entry layout

The current frontend is still split by route via:

- `frontend/src/entries/index.ts`
- `frontend/src/entries/service.ts`
- `frontend/src/entries/gap.ts`
- `frontend/src/entries/matches.ts`

### 5.3 Existing Flask template shells

The current UI is still served through multiple Jinja shells:

- `templates/index.html`
- `templates/service.html`
- `templates/gap.html`
- `templates/matches.html`

### 5.4 Existing Flask asset integration

- `pricewatch/web/assets.py`
- `pricewatch/app_factory.py`
- `pricewatch/web/context.py`

These already provide a strong base for Vite asset wiring and can be reused for a single SPA shell.

## 6. Confirmed decisions captured by this RFC

The following decisions are already resolved and are not open questions for this RFC:

1. the target UI architecture is a **single Vue SPA**;
2. Flask remains the **backend/API owner**;
3. operator UI routes are served through a **single Flask SPA shell**;
4. Vue Router is introduced with **history mode**;
5. shared client state uses **Pinia**, but only where shared state truly exists;
6. route-specific bootstrap/config moves to a **shared SPA bootstrap/config model**;
7. coexistence with the current multi-entry model is allowed only as a short-lived transition;
8. the end state removes route-level ownership from `templates/index.html`, `templates/service.html`, `templates/gap.html`, and `templates/matches.html`.

## 7. Target architecture

### 7.1 Frontend runtime model

The operator UI becomes one Vue application that owns:

- shell layout;
- navigation;
- route transitions;
- route-level page composition;
- shared client-side state;
- frontend-only loading and error surfaces.

The SPA should be structured around:

- `frontend/src/main.ts`
- `frontend/src/App.vue`
- `frontend/src/router/`
- `frontend/src/stores/`
- `frontend/src/layouts/`
- `frontend/src/pages/`

### 7.2 Backend/runtime model

Flask remains responsible for:

- operator and admin API routes under `pricewatch/web/`;
- application configuration and backend dependency wiring;
- serving the SPA shell template;
- serving or referencing built frontend assets;
- returning backend/API errors and server-side HTTP statuses where appropriate.

Flask is no longer responsible for owning route-specific operator HTML documents.

### 7.3 Shell model

The target shell becomes one template, for example:

- `templates/spa.html`

This shell is responsible only for:

- mounting the SPA root element;
- including the SPA entry assets;
- providing minimal bootstrap config.

It is not responsible for rendering operator-page-specific markup.

### 7.4 Router model

The SPA router becomes the canonical operator navigation model.

Expected first-class routes include:

- `/` → comparison
- `/service` → service console
- `/gap` → gap review
- `/matches` → confirmed product mappings

Additional nested routes may be introduced later if they materially improve UX, but this RFC does not require route proliferation beyond the current page boundaries.

### 7.5 Shared state model

Pinia is adopted for:

- cross-route reference data that is reused in multiple views;
- shell-level state;
- route-independent caches that outlive a single component tree.

Pinia is **not** used as a blanket replacement for all local component/composable state. Page-local and workflow-local state may remain in composables where appropriate.

## 8. Routing and fallback behavior

### 8.1 Browser history mode

The SPA uses Vue Router history mode.

This means direct requests to SPA-managed routes must receive the SPA shell from Flask rather than a 404.

### 8.2 Flask responsibilities for UI routes

Flask must provide a controlled fallback for SPA-owned operator paths so that:

- direct navigation to `/service` works;
- browser refresh on `/gap` works;
- deep links into supported SPA routes work;
- unsupported API or non-UI routes do not silently route into the SPA by mistake.

### 8.3 404 responsibility split

The split must be explicit:

- unknown backend/API routes remain server-side errors or 404s;
- unknown SPA-managed frontend paths render the SPA shell and then resolve to a client-side Not Found route.

This avoids blurring backend route errors with client navigation errors.

## 9. SPA bootstrap/config model

The current multi-page setup can inject route-local data through templates. In the SPA model, this must be replaced with one shared bootstrap/config strategy.

This RFC standardizes the following default approach:

1. a small inline bootstrap object is rendered by Flask into the SPA shell;
2. this object contains only configuration that must exist before the SPA can initialize;
3. page and workflow data continue to load through normal API calls;
4. bootstrap content remains minimal and must not become a shadow data-fetch channel.

Typical bootstrap content may include:

- environment flags;
- frontend mode flags;
- route-agnostic UI configuration;
- URLs or feature toggles needed before app mount.

Route-local business data should not be embedded into the shell unless there is a strong startup reason.

## 10. Repository-aligned implementation scope

This RFC expects the implementation to evolve the current repository structure rather than discard it.

### 10.1 Reused foundation

The following existing frontend layers should be reused, not rewritten from scratch:

- `frontend/src/api/`
- `frontend/src/components/base/`
- `frontend/src/composables/`
- `frontend/src/pages/comparison/`
- `frontend/src/pages/gap/`
- `frontend/src/pages/matches/`
- `frontend/src/pages/service/`

### 10.2 Structural changes expected

The implementation is expected to introduce or consolidate:

- `frontend/src/main.ts`
- `frontend/src/App.vue`
- `frontend/src/router/`
- `frontend/src/stores/`
- optional shared layout folders such as `frontend/src/layouts/`

### 10.3 Transitional artifacts expected to be removed by the end state

- `frontend/src/entries/index.ts`
- `frontend/src/entries/service.ts`
- `frontend/src/entries/gap.ts`
- `frontend/src/entries/matches.ts`
- `templates/index.html`
- `templates/service.html`
- `templates/gap.html`
- `templates/matches.html`

These may temporarily coexist during migration, but they are not part of the target state.

## 11. Migration strategy

The migration should be implemented as a controlled cutover from multi-entry to single-entry, not as a speculative rewrite.

### 11.1 Phase A — architecture and shell groundwork

This phase introduces:

- ADR acceptance and documentation alignment;
- SPA root application structure;
- router foundation;
- shell/layout consolidation;
- app bootstrap/config plumbing.

No page workflow should be behaviorally rewritten in this phase unless required by shell integration.

### 11.2 Phase B — route integration

This phase moves existing page implementations behind the SPA router while preserving existing behavior as much as possible.

The intent is to preserve the already built Vue page logic and re-home it within one SPA rather than rebuild those pages from scratch.

### 11.3 Phase C — Flask cutover

This phase replaces page-specific Flask UI routes and template shells with the SPA shell routing model.

The Flask/UI layer should still remain explicit and observable:

- API routes stay independent;
- UI route fallback stays narrowly scoped;
- server-side logs should still identify operator route hits meaningfully.

### 11.4 Phase D — cleanup and hardening

This phase removes transitional multi-entry artifacts, aligns documentation, and expands tests for the new routing model.

## 12. Testing and verification expectations

The SPA transition must not rely on manual confidence alone.

Minimum verification expectations include:

### 12.1 Frontend unit/component coverage

Preserve and extend the existing frontend test investment for:

- route mounting;
- shell rendering;
- route transitions;
- bootstrap/config parsing;
- any new Pinia stores.

### 12.2 Backend integration coverage

Add backend-facing tests for:

- SPA shell rendering in development mode;
- SPA shell rendering in manifest/build mode;
- Flask fallback behavior for SPA-managed routes;
- non-SPA routes remaining outside the fallback path.

### 12.3 Manual smoke checks

At minimum, release validation must verify:

- direct browser load on `/`;
- direct browser load on `/service`;
- direct browser load on `/gap`;
- direct browser load on `/matches`;
- browser refresh on those routes;
- navigation between those routes without full document reload;
- expected handling of an unknown SPA path;
- expected handling of an unknown API path.

## 13. Rollback posture

This RFC assumes the migration will be implemented in a staged way with explicit rollback points.

Rollback should be possible at least until the final cutover phase by retaining:

- the current multi-entry asset path;
- the current page template path;
- isolated commits for shell/routing changes;
- isolated commits for cleanup/removal.

Once the repository fully cuts over to the SPA shell and removes transitional templates/entries, rollback becomes a code rollback to a prior revision rather than a runtime toggle.

That is acceptable as long as the cutover commit sequence is clear and reversible during review.

## 14. Risks and mitigations

### 14.1 Route fallback overreach

**Risk:** Flask SPA fallback may accidentally intercept routes that should remain API/server owned.

**Mitigation:** keep fallback scope explicit and limited to operator UI paths.

### 14.2 Bootstrap config sprawl

**Risk:** the SPA shell becomes a dumping ground for route/business data.

**Mitigation:** keep shell bootstrap minimal; business data continues to load via APIs.

### 14.3 Over-centralized client state

**Risk:** Pinia becomes a catch-all and obscures local component ownership.

**Mitigation:** restrict Pinia to genuinely shared app state; keep page-local state in composables/components.

### 14.4 Hidden behavior drift during re-homing

**Risk:** existing page behavior changes unintentionally when moved under the router.

**Mitigation:** preserve page contracts first; prefer re-homing over redesign.

### 14.5 Documentation drift

**Risk:** repository docs keep describing the hybrid multi-entry state after cutover.

**Mitigation:** docs sync is a required part of the rollout, not a follow-up nice-to-have.

## 15. Acceptance criteria

This RFC is considered successfully implemented when all of the following are true:

1. the operator UI is served through one SPA shell;
2. the frontend build has one canonical SPA entrypoint;
3. router-managed navigation covers the current operator page set;
4. Flask no longer owns separate page-specific operator shells;
5. direct browser entry and refresh work on SPA routes;
6. API routes remain server-owned and are not masked by SPA fallback;
7. shared state is centralized only where it materially helps;
8. documentation and CI reflect the SPA architecture rather than the transitional hybrid state.

## 16. Out of scope follow-ups

The following items may become future work after the SPA cutover but are not required for this RFC:

- deeper route decomposition inside `/service`;
- more aggressive client-side caching strategies;
- optimistic mutation updates across the entire SPA;
- shell-level notifications/toasts infrastructure;
- broader visual redesign or component-system expansion;
- frontend performance tuning beyond what is required for correctness.

## 17. Recommended implementation order

A repository-aligned rollout should roughly follow this order:

1. formalize ADR-0015 and documentation alignment;
2. add SPA root structure (`main.ts`, `App.vue`, router, stores);
3. introduce shared SPA shell template and app bootstrap model;
4. re-home current page Vue apps into router-managed views;
5. move shell/nav/tab ownership into SPA layouts/components;
6. convert Flask UI routes to serve the SPA shell with explicit fallback behavior;
7. collapse Vite output to a single SPA entrypoint;
8. remove old multi-entry and multi-template artifacts;
9. expand CI/tests/docs for the new architecture.

This order intentionally separates:

- architecture definition;
- SPA shell creation;
- route migration;
- Flask cutover;
- cleanup.

That separation keeps the migration reviewable and reversible.
