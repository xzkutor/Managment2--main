# ADR-0015: Transition from Incremental Vue-over-Flask Pages to a Full Vue SPA

- **Status:** Accepted — implemented
- **Date:** 2026-03-29
- **Implemented:** 2026-03-29
- **Decision Makers:** Project maintainers
- **Supersedes / Updates:** ADR-0014 Incremental Vue 3 Adoption over Flask Templates
- **Related:** ADR-0009 UI Polish and Structured Visual Fields, ADR-0010 Production Runtime Topology: Web + Scheduler + Workers, ADR-0012 Product Match Review Workflow, ADR-0013 HTTP Page Cache TTL Configuration

> **Implementation note (post-cutover):** The SPA transition described in this ADR is
> complete. `templates/spa.html` is the single shell; `frontend/src/main.ts` is the
> single entry point; left-sidebar navigation is canonical via `AppShellSidebarNav`;
> `AppShellHeader` is strictly a page-title/subtitle component. The post-cutover
> stabilization workstream (Commits 1–6 in `plans/post-cutover-stabilization-copilot-plan.md`)
> hardened mutation UX — comparison decisions and auto-link now patch local state without
> full page-level refetches.

## Context

The repository has already completed most of the incremental Vue rollout approved in ADR-0014.

The current state is no longer a Flask application with isolated legacy JavaScript pages. Instead, the repository now has:

- a dedicated `frontend/` workspace built on **Vue 3 + Vite + TypeScript**;
- Vue page roots for `/`, `/service`, `/gap`, and `/matches`;
- page-specific TypeScript entry points under `frontend/src/entries/`;
- Flask/Vite asset integration via `pricewatch/web/assets.py` and `vite_asset_tags(...)`;
- server-rendered HTML shells that mainly provide header/nav, page title, CSS includes, and mount roots.

That means the project has already crossed the most expensive part of frontend modernization: componentization, typed API adapters, page-level Vue state, and a dedicated frontend toolchain now exist.

However, the current architecture is still **multi-page Vue mounted over Flask-owned page shells**, which has several drawbacks:

1. application shell concerns are duplicated across multiple templates;
2. navigation is still hard route-to-route page navigation instead of in-app client navigation;
3. shared state and cross-page UX are constrained by separate page entry boundaries;
4. each page has its own mount/bootstrap path, which increases shell and asset maintenance;
5. configuration injection still uses page-specific template globals such as `SERVICE_CONFIG`;
6. direct navigation, loading, and page transitions remain shaped by Flask page ownership rather than a single frontend application model.

At the same time, the current repository already contains the pieces needed for a full SPA migration without restarting frontend work from scratch.

## Problem Statement

The project must decide whether to keep the current hybrid model as the long-term frontend architecture or to consolidate the existing Vue pages into a **single full SPA** while keeping Flask as an API/backend host.

## Decision

The project will transition from the current multi-page Vue-over-Flask model to a **single Vue SPA**.

Flask will remain the backend and API owner, but it will stop being the owner of page-specific UI shells for operator-facing routes.

## Decision Summary

The approved direction is:

- keep **Vue 3 + Vite + TypeScript** as the frontend stack;
- adopt **Vue Router** for client-side route ownership;
- adopt **Pinia** as the default application-level shared state mechanism;
- move from multiple page entry points to a **single SPA entry point**;
- replace multiple Flask HTML shells with a **single SPA shell template**;
- keep Flask as the owner of backend routing, API endpoints, auth/session behavior, config, and deployment/runtime composition;
- serve the SPA shell from Flask for all operator-facing UI routes;
- move operator-facing navigation, page layout, and route transitions into Vue.

## Decision Drivers

- The repository already contains a substantial Vue frontend, so the marginal cost of SPA consolidation is lower than starting a new frontend strategy.
- Operator workflows span multiple pages and would benefit from shared state, consistent navigation, and one application shell.
- The current multi-entry page model duplicates shell concerns and increases maintenance overhead.
- The frontend now has enough page coverage to justify router-based composition.
- Moving to SPA navigation reduces hard page transitions and opens the door to better loading UX.
- Consolidation is easier now than after more page-specific shells and bootstrap patterns accumulate.

## Architectural Rules

### 1. Flask remains backend/API owner, not frontend page owner

Flask continues to own:

- API routes and backend orchestration;
- database/session access and server-side business logic;
- deployment/runtime composition;
- app config and environment loading;
- auth/session/cookie behavior;
- operational concerns outside the browser runtime.

Flask no longer owns separate operator-facing UI pages such as `index.html`, `service.html`, `gap.html`, and `matches.html` as independent frontend shells.

### 2. One SPA shell replaces multiple page shells

The target end state is a single Flask-served shell template (for example `templates/spa.html`) that mounts one Vue app.

The current templates should be treated as transitional and removed after the SPA cutover.

### 3. One frontend entry replaces multiple page entries

The target frontend entry model is:

- one `main.ts` entry;
- one `App.vue` application root;
- one router tree;
- route-level page components.

Current page entry files under `frontend/src/entries/` are transitional and should be removed after the cutover.

### 4. Vue Router is the route owner for operator-facing UI

Operator-facing routes such as:

- `/`
- `/service`
- `/gap`
- `/matches`

should be represented as Vue Router routes.

Flask should serve the SPA shell for those routes and allow client-side routing to own navigation after the initial page load.

### 5. Pinia becomes the default shared state boundary

The project will adopt Pinia for state that must survive route transitions or be shared across route-level modules, such as:

- app shell state;
- store/category reference data caches;
- route-independent UI configuration;
- cross-page selection or refresh triggers where justified.

Pinia should not be used as a dumping ground for all page-local state. Page-local ephemeral state may remain inside route composables/components.

### 6. The backend API remains the primary contract

The SPA transition does not authorize a broad backend redesign in the first wave.

Existing `/api/...` endpoints remain the primary boundary. Any API normalization should be incremental and should happen behind typed frontend adapters or separately approved backend changes.

### 7. The SPA shell owns navigation, layout, and shared chrome

The following responsibilities move from Flask templates into Vue layout components:

- top navigation;
- shared page chrome/header structure;
- route transitions;
- shared loading/error layout behavior.

Flask templates should stop encoding UI navigation semantics beyond serving the root shell.

### 8. Route-specific inline config injection must be minimized

Current route-specific inline injections such as `SERVICE_CONFIG` are transitional.

The SPA migration should replace them with one of the following approved patterns:

- a single shared bootstrap payload attached to the SPA shell;
- dedicated lightweight `/api/app-config` or equivalent endpoint;
- a small number of deterministic `data-*` or JSON bootstrap values on the SPA root.

The project should avoid continuing page-specific template script globals.

### 9. No SSR/Nuxt adoption in this transition

This decision is for a **client-rendered SPA**.

The project will not introduce:

- Nuxt;
- SSR;
- server components;
- a second frontend platform.

### 10. No long-term hybrid ownership after cutover

Temporary coexistence is acceptable during migration, but the target end state is explicit:

- Vue owns operator-facing UI routes;
- Flask owns API/backend/runtime concerns.

The repository should not keep long-term dual ownership where Flask still meaningfully owns per-page UI shells while Vue also owns route-level rendering.

## Migration Shape

The migration should proceed in the following order:

1. approve the architecture change in ADR form;
2. resolve the remaining open design questions;
3. formalize the transition in an RFC;
4. introduce SPA scaffolding (`main.ts`, `App.vue`, `router`, `stores`);
5. migrate current page components into router views;
6. introduce a Vue app shell/layout;
7. collapse Flask page routes into a single SPA shell response;
8. remove transitional entry points and legacy multi-shell templates;
9. update CI, docs, and release checklists.

## Consequences

### Positive

- One coherent frontend application model.
- Client-side navigation across operator-facing routes.
- Easier sharing of state and reference data across routes.
- Lower long-term maintenance overhead for shells and page bootstrapping.
- Cleaner separation: Flask as backend/API, Vue as frontend app.
- Better foundation for future UX improvements without repeating shell code.

### Negative / Costs

- The project must now own SPA routing and history-mode integration.
- Router-level navigation and app boot must be tested more thoroughly.
- The team must define clear rules for Pinia usage versus page-local state.
- Existing shell templates and bootstrap patterns become migration debt to remove.
- Direct route loads and deep-link behavior need explicit backend handling.

### Risks

- Partial migration may leave the repository in an awkward hybrid state if not completed.
- Route/bootstrap/config behavior may drift if a shared app-config strategy is not defined early.
- An uncontrolled move to global stores could create unnecessary coupling.
- Docs may lag behind if ADR-0014-era language is not explicitly superseded.

## Status of ADR-0014

ADR-0014 was correct for the earlier repository state and enabled the current Vue foundation.

This ADR does **not** treat ADR-0014 as a mistake. Instead, it records that the project has progressed far enough that the previous incremental end state is no longer the preferred long-term architecture.

ADR-0014 should therefore be treated as:

- historically valid;
- operationally superseded for the target end state;
- still relevant as migration history.

## Follow-Up Required

This ADR requires a follow-up RFC covering:

- SPA shell and routing model;
- Flask fallback behavior for history-mode routes;
- app-config/bootstrap strategy;
- Pinia ownership boundaries;
- migration sequencing and cutover criteria;
- testing and release strategy;
- rollback shape during transition.
