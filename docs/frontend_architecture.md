# Frontend Architecture

## Overview

The frontend is built with **Vue 3 + Vite 5 + TypeScript**. Flask remains the routing and page-shell owner; Vue is mounted incrementally per page. There is no SPA rewrite, no Vue Router, and no Pinia.

Each operator-facing page is served as a regular Flask HTML response. Vue is mounted inside a single `<div id="...-app"></div>` root per page. All interactive UI — cascade loading, comparison execution, decisions, manual picker — is owned by Vue. Flask owns the header, nav, CSS includes, and the page `<title>`.

---

## Entry Points

Each page has one TypeScript entry under `frontend/src/entries/`:

| File | Flask route | Vue mount root | Root component |
|---|---|---|---|
| `src/entries/index.ts` | `/` | `#comparison-app` | `ComparisonPage.vue` |
| `src/entries/service.ts` | `/service` | `#serviceApp` | `ServicePage.vue` |
| `src/entries/gap.ts` | `/gap` | `#gap-app` | `GapPage.vue` |
| `src/entries/matches.ts` | `/matches` | `#matches-app` | `MatchesPage.vue` |

Each entry:
- guards the mount (`if (!el) return`);
- calls `createApp(PageComponent).mount(el)`;
- does not assume SPA or router ownership.

---

## Source Tree

```
frontend/
├── src/
│   ├── entries/          # Vite entry points (one per page)
│   ├── pages/            # Page-level modules
│   │   ├── comparison/   # / — comparison page
│   │   │   ├── ComparisonPage.vue
│   │   │   ├── api.ts             # Thin API wrappers for this page
│   │   │   ├── types.ts           # DTO types for this page
│   │   │   ├── components/        # Page-specific Vue components
│   │   │   │   ├── shared/        # Micro-components reused within the page
│   │   │   │   └── *.vue
│   │   │   └── composables/       # Page-scoped composables
│   │   ├── gap/          # /gap — gap review page
│   │   ├── matches/      # /matches — confirmed matches page
│   │   └── service/      # /service — service console page
│   ├── components/       # Shared Vue components (BaseButton, EmptyState, StatusPill, …)
│   ├── composables/      # Shared composables (useAsyncState, …)
│   ├── api/              # Shared HTTP layer
│   │   ├── http.ts       # Low-level fetch wrapper (requestJson)
│   │   ├── client.ts     # Page-agnostic API helpers (fetchStores, fetchCategoriesForStore, …)
│   │   ├── errors.ts     # ApiError class
│   │   └── adapters/     # Response shape adapters (stores, mappings, scheduler)
│   ├── types/            # Shared frontend DTO types
│   │   ├── common.ts
│   │   ├── store.ts
│   │   ├── scheduler.ts
│   │   ├── mappings.ts
│   │   └── …
│   ├── styles/           # Global/shared CSS imported into entries
│   └── test/             # Vitest unit and component tests
│       ├── api/
│       ├── components/
│       ├── composables/
│       └── pages/
│           ├── comparison/
│           ├── gap/
│           ├── matches/
│           └── service/
├── vite.config.ts
├── vitest.config.ts
├── tsconfig.json
└── package.json
```

---

## Per-Page Structure Convention

Every page module under `frontend/src/pages/<page>/` follows this layout:

```
<page>/
├── <PageName>Page.vue        # Root component — mounts sub-components, calls composable
├── api.ts                    # Thin wrappers for this page's backend endpoints only
├── types.ts                  # DTO types mirroring backend API shapes for this page
├── components/               # Components used only on this page
│   ├── shared/               # Micro-components reused within the page (badges, links, pills)
│   └── *.vue
└── composables/
    └── use<PageName>Page.ts  # Primary page-state composable
```

The root page component:
- instantiates the primary composable with `const page = use<PageName>Page()`;
- calls the initial data load in `onMounted`;
- passes state to child components as props;
- routes events back to composable actions.

---

## Composable Conventions

Page composables (`use<Page>Page.ts`) own:
- all reactive state (`ref`, `computed`);
- async data loading;
- action handlers (compare, makeDecision, etc.).

They **must not**:
- commit sessions or call Flask directly (that is `api.ts`'s job);
- be shared across pages.

Shared composables (`frontend/src/composables/`) are page-agnostic utilities (e.g. `useAsyncState`).

---

## API Layer

`frontend/src/api/http.ts` — low-level typed `fetch` wrapper (`requestJson`). Converts non-2xx responses to `ApiError`. Never calls business logic.

`frontend/src/api/client.ts` — page-agnostic endpoint helpers (`fetchStores`, `fetchCategoriesForStore`, scheduler CRUD, mappings, etc.). Uses adapters from `api/adapters/` to normalize raw server shapes into stable frontend DTOs.

`frontend/src/pages/<page>/api.ts` — page-scoped thin wrappers for endpoints only that page uses. Re-exports shared helpers where needed so callers import from one place.

**Rules:**
- Never use `fetch` or `axios` directly in components or composables — always go through `requestJson`.
- Never reshape backend contracts aggressively — use thin adapters only.
- Never import page-specific `api.ts` from a different page's code.

---

## Flask ↔ Vite Integration

Integration is handled by `pricewatch/web/assets.py`, which exposes `vite_asset_tags(entry)` as a Jinja global.

**Dev mode** (`VITE_USE_DEV_SERVER=True`):
- Set `VITE_DEV_SERVER_URL=http://localhost:5173` in Flask config.
- `vite_asset_tags()` emits a `<script type="module" src="http://localhost:5173/...">` tag pointing to the Vite dev server.
- Hot module replacement (HMR) works automatically.

**Production** (`npm run build`):
- Vite writes hashed assets to `static/dist/` and a manifest to `static/dist/.vite/manifest.json`.
- `vite_asset_tags()` reads the manifest and emits correct `<link rel="stylesheet">` + `<script type="module">` tags.

**Jinja usage in templates:**
```html
{{ vite_asset_tags('src/entries/index.ts') }}
```

---

## Static Assets Policy

| Path | Purpose |
|---|---|
| `static/css/common.css` | **Active** — shared base styles used by all pages; referenced via `<link>` in each template. |
| `static/css/<page>.css` | **Active** — page-specific styles (`index.css`, `service.css`, `gap.css`, `matches.css`). |
| `static/dist/` | **Generated** — Vite build output; not committed. |

All legacy page-specific scripts (`index.js`, `gap.js`, `matches.js`, `service.js`, `service.*.js`, `common.js`) have been removed. Each page template now contains only: Flask-owned `<link>` CSS tags, the `SERVICE_CONFIG` bootstrap object where needed (`/service`), and `{{ vite_asset_tags(...) }}`.

---

## Testing

Frontend tests use **Vitest** and **@vue/test-utils**.

```bash
cd frontend
npm test                    # run all tests (watch mode off)
npm test -- --reporter=verbose   # with per-test output
npm run build               # vue-tsc --noEmit + vite build (full type check)
```

Test files live under `frontend/src/test/` mirroring the source tree:

| Test path | What it covers |
|---|---|
| `test/api/` | `requestJson`, `ApiError` |
| `test/components/` | Shared Vue components |
| `test/composables/` | Shared composables |
| `test/pages/comparison/` | `useComparisonPage`, `useManualPicker`, comparison components |
| `test/pages/gap/` | Gap page composable and components |
| `test/pages/matches/` | Matches page composable and components |
| `test/pages/service/` | Service page tabs and components |

**Conventions:**
- Mock API modules at the top of each test file using `vi.mock(...)`.
- Use `flushPromises()` after async operations.
- Test composables directly (not through a wrapper component) for logic coverage.
- Test components for rendered output, emitted events, and prop-driven state.

---

## Guardrails

- **No Vue Router.** Flask owns routing. Vue does not navigate between pages.
- **No Pinia.** State lives in composables, scoped to one page.
- **No inline `onclick` handlers** in Flask templates. All interactions are Vue-owned.
- **No `window.*` global action handlers.** Legacy globals (`window.runComparison`, etc.) have been removed.
- **No parallel DOM/Vue ownership.** Each page has exactly one owner after migration.
- **Do not import page `api.ts` across pages.** Shared API helpers belong in `frontend/src/api/client.ts`.

