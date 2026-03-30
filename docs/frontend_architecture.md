# Frontend Architecture

## Overview

The frontend is a **Vue 3 + Vite 5 + TypeScript SPA** served through a single
Flask-rendered shell (`templates/spa.html`). Flask owns the backend API (`/api/*`)
and serves `spa.html` for all operator-facing UI routes. Vue Router owns all
client-side navigation.

This is a SPA architecture. Flask does **not** render per-page HTML anymore — it
returns `spa.html` for every UI route and returns JSON for every `/api/*` route.

---

## SPA Entry Point

One Vite entry point — `frontend/src/main.ts`:

- Creates the Vue application, registers Pinia and Vue Router, mounts `App.vue` on `#app`.
- `App.vue` renders `AppShellLayout`, which hosts the shared header/nav and a `<RouterView>`.
- All four operator pages and the `NotFoundPage` are lazy-loaded by the router.

The manifest key is `src/main.ts` (Vite uses the source path as the key).
Flask loads it via `{{ vite_asset_tags('src/main.ts') }}` in `templates/spa.html`.

---

## Route Table

`frontend/src/router/routes.ts` declares all client-side routes:

| Path | Route name | Component |
|---|---|---|
| `/` | `comparison` | `ComparisonRouteView.vue` |
| `/service` | `service` | `ServiceRouteView.vue` |
| `/gap` | `gap` | `GapRouteView.vue` |
| `/matches` | `matches` | `MatchesRouteView.vue` |
| `/:pathMatch(.*)*` | `not-found` | `NotFoundPage.vue` |

Route `meta.title` and `meta.subtitle` are read by `AppShellHeader` to render the
per-route header band without per-page shell duplication.

### Flask ↔ Vue Router handoff

`pricewatch/web/ui_routes.py` (`ui_bp`):
- Explicit routes (`/`, `/service`, `/gap`, `/matches`, `/app/*`) → serve `spa.html`.
- `@ui_bp.app_errorhandler(404)` catch-all → serve `spa.html` for any non-`/api/` path.
- `/api/*` 404s → pass through as JSON errors.

Route `meta.title` and `meta.subtitle` are read by `AppShellHeader` to render the
per-route page heading.

---

## Application Shell

```
App.vue
└── AppShellLayout.vue
    ├── .app-shell-sidebar
    │   └── AppShellSidebarNav.vue   ← canonical app navigation (left sidebar)
    └── .app-shell-content
        ├── AppShellHeader.vue       ← page title/subtitle from route.meta only
        └── <main>
            └── <RouterView />       ← active page component mounts here
```

**Navigation ownership:**
- `AppShellSidebarNav` owns **all** canonical app navigation links (`/`, `/service`, `/gap`, `/matches`).
  Link definitions are centralized in `frontend/src/constants/navigation.ts` — not duplicated in any component.
- `AppShellHeader` renders **only** the per-route title and subtitle from `route.meta`.
  It does **not** contain any navigation links.
- The sidebar is always visible: on wide screens it is a fixed left column;
  on narrow screens it stacks above the content area.

---

## Source Tree

```
frontend/
├── src/
│   ├── main.ts               ← SPA entry point
│   ├── App.vue               ← Root component
│   ├── router/
│   │   ├── index.ts          ← createRouter (history mode + scrollBehavior)
│   │   └── routes.ts         ← Route table + RouteMeta augmentation
│   ├── layouts/
│   │   └── AppShellLayout.vue
│   ├── pages/
│   │   ├── comparison/       ← / — comparison page
│   │   │   ├── ComparisonRouteView.vue
│   │   │   ├── ComparisonPage.vue
│   │   │   ├── api.ts
│   │   │   ├── types.ts
│   │   │   ├── components/
│   │   │   └── composables/
│   │   ├── service/          ← /service — service console
│   │   ├── gap/              ← /gap — gap review
│   │   ├── matches/          ← /matches — confirmed matches
│   │   └── NotFoundPage.vue  ← Client-side 404 (catch-all route)
│   ├── components/           ← Shared Vue components (AppShellHeader, AppShellSidebarNav, BaseButton, …)
│   ├── constants/            ← Shared constants (navigation.ts — canonical nav link definitions)
│   ├── composables/          ← Shared composables (useAsyncState, …)
│   ├── api/
│   │   ├── http.ts           ← Low-level typed fetch wrapper (requestJson)
│   │   ├── client.ts         ← Page-agnostic endpoint helpers
│   │   ├── errors.ts         ← ApiError class
│   │   └── adapters/         ← Response-shape normalizers
│   ├── stores/               ← Pinia stores
│   ├── types/                ← Shared DTO types
│   ├── styles/               ← Global/shared CSS imported by main.ts
│   └── test/                 ← Vitest unit and component tests
│       ├── router/           ← Router contract tests
│       ├── api/
│       ├── components/
│       ├── composables/
│       └── pages/
├── vite.config.ts
├── vitest.config.ts
├── tsconfig.json
└── package.json
```

---

## Workspace Pages

### `/comparison` — Two-column operator workspace (RFC-016 v2)

```
ComparisonPage.vue
├── ComparisonControlRail.vue        ← left sticky rail (260 px)
│   ├── <select> target store        ← single selector; no reference-store selector
│   ├── ReferenceCategoryList.vue    ← plain selectable rows; shows product_count badge
│   └── compare button + status
├── ComparisonSummaryBar.vue         ← context strip + four KPI cards
├── ComparisonWorkspacePlaceholder   ← shown when comparisonWorkspaceState === 'idle'
├── ComparisonCollapsibleSection     ← shared collapsible shell (collapsed by default)
│   ├── AutoSuggestionsTable.vue     ← confirmed_matches where is_confirmed=false
│   ├── CandidateGroups.vue / CandidateGroupCard.vue  ← needs-choice groups
│   └── ReferenceOnlySection.vue    ← reference-only items
├── TargetOnlySection.vue            ← secondary <details>-collapsed section
└── ManualPickerDrawer.vue           ← shared right-side drawer (one instance on page)
```

**State machine** (`comparisonWorkspaceState` in `useComparisonPage`):

| State | Condition | UI shown |
|---|---|---|
| `idle` | no compare triggered yet | `ComparisonWorkspacePlaceholder` |
| `comparing` | fetch in progress | `ComparisonSummaryBar` loading state |
| `review` | results available, ≥1 review item | collapsible sections (all collapsed by default) |
| `empty` | compared, zero review items | "Все зіставлено!" empty state |
| `error` | compare API failure | error banner |

**Category rail counts:** The `product_count` field is always returned by
`GET /api/stores/:id/categories` and rendered as a badge next to each category name.
Zero-count categories are marked with `.cw-cat-count--empty` for visual distinction.

**Section collapse policy:** All three primary sections (`autoSuggestions`,
`candidateGroups`, `referenceOnly`) start collapsed (`sectionExpanded` defaults to
`false`). Collapse state resets on every new compare run.

**Manual picker:** One `ManualPickerDrawer` instance lives on `ComparisonPage`.
Any candidate-group card or reference-only item opens it via `open-picker` event.

---

### `/matches` — Three-zone workspace

```
MatchesPage.vue
├── aside.mw-rail                    ← left filter rail (sticky)
│   └── MatchesFilters.vue           ← store/category/status filters; no search input here
├── .mw-content
│   ├── .mw-header.panel             ← search bar + KPI summary
│   │   └── MatchesSummary.vue       ← three KPI cards (total/confirmed/rejected)
│   └── .mw-results.panel            ← results table
│       └── MatchesTable.vue / MatchesTableRow.vue
```

**Search vs. filters split:** The text search input lives in `.mw-header` (workspace
top), not in `MatchesFilters`. `MatchesFilters` owns store/category/status selectors
only — this keeps the filter rail compact and the search bar visually dominant.

**Active filter badge:** `MatchesFilters` shows a `.mw-rail-badge` counter when
`activeFiltersCount > 0`, giving the operator a quick sense of how many criteria are
active without expanding the rail.

**Non-destructive load policy:** `loadMappings()` keeps existing rows visible while
the new request is in-flight (`isLoadingRows=true`). Only on success are `rows`
replaced. This avoids table flash on filter/refresh.

---

### `/gap` — Gap analysis workspace

```
GapPage.vue
├── aside.gap-workspace-rail.panel   ← sticky left rail
│   └── GapFilters.vue               ← structured 4-section filter rail:
│       ├── Section 1: Ціль          ← target store selector
│       ├── Section 2: Категорія     ← reference category + mapped target categories
│       ├── Section 3: Пошук і фільтри ← text search, availability toggle, status checkboxes
│       └── Section 4: Дія           ← primary load/refresh button
└── .gap-workspace-main
    └── .gap-workspace-main-surface
        ├── GapSummary.vue           ← compact KPI strip + context header (shown after load)
        ├── GapStatusBanner.vue      ← in-surface status states
        ├── GapPreRunPlaceholder.vue ← shown before first load (hasNeverLoaded)
        └── GapGroupTable.vue[]      ← one panel per mapped target category
```

**Workspace state model** (`useGapData` helpers):

| Helper | Condition | UI effect |
|---|---|---|
| `hasNeverLoaded` | `!hasLoaded && !loading && !error` | `GapPreRunPlaceholder` is visible |
| `hasResults` | `hasLoaded && groups.length > 0` | group panels visible |
| `isEmptyAfterLoad` | `hasLoaded && groups.length === 0` | `GapStatusBanner` empty state |
| `hasBlockingError` | `!!error` | `GapStatusBanner` error state |

**Status banner modes** (`GapStatusBanner`):

| Mode | Condition | UI shown |
|---|---|---|
| `refreshing` | `loading && hasLoaded` | subtle inline bar — old results remain visible |
| `initialLoading` | `loading && !hasLoaded` | full block loading indicator |
| `error` | `!!errorText` | `.error` block with message |
| `isEmpty` | `isEmpty && hasLoaded` | `.empty-state` panel ("Розрив відсутній") |
| silent | loaded with results, no error | renders nothing (`<!--v-if-->`) |

**Non-destructive reload policy:** Results are never blanked during a refresh —
`GapStatusBanner` shows a gentle `gap-surface-refreshing` bar while keeping group
panels mounted. `patchGapResult.ts` applies local optimistic updates so the page
does not need to re-fetch on every status mutation.

**Group panels:** Each mapped target category renders as one self-contained
`.gap-group-panel` with a heading, item count badge, and compact `.gap-row` rows.
Row action buttons are disabled (not hidden) while `actionInProgressId` is set, and
a `.gap-row-action-pending` spinner is shown next to the in-flight row.

**Context header:** `GapSummary` receives `targetStoreName`, `refCategoryName`, and
`targetCatCount` from `GapPage` computed helpers (derived from `useGapFilters` state —
no extra API calls).

---


Every page module under `frontend/src/pages/<page>/` follows this layout:

```
<page>/
├── <PageName>RouteView.vue   ← Thin wrapper; registered in router/routes.ts
├── <PageName>Page.vue        ← Root component — mounts sub-components, calls composable
├── api.ts                    ← Thin wrappers for this page's backend endpoints only
├── types.ts                  ← DTO types mirroring backend API shapes for this page
├── components/               ← Components used only on this page
│   ├── shared/               ← Micro-components reused within the page
│   └── *.vue
└── composables/
    └── use<PageName>Page.ts  ← Primary page-state composable
```

---

## Composable Conventions

Page composables (`use<Page>Page.ts`) own:
- all reactive state (`ref`, `computed`);
- async data loading;
- action handlers (compare, makeDecision, etc.).

They **must not**:
- call Flask directly (that is `api.ts`'s job);
- be shared across pages.

Shared composables (`frontend/src/composables/`) are page-agnostic utilities.

---

## API Layer

`frontend/src/api/http.ts` — low-level typed `fetch` wrapper (`requestJson`). Converts non-2xx responses to `ApiError`. Never calls business logic.

`frontend/src/api/client.ts` — page-agnostic endpoint helpers (`fetchStores`, `fetchCategoriesForStore`, scheduler CRUD, mappings, etc.). Uses adapters from `api/adapters/` to normalize raw server shapes.

`frontend/src/pages/<page>/api.ts` — page-scoped thin wrappers for endpoints only that page uses.

**Rules:**
- Never use `fetch` or `axios` directly in components or composables — always go through `requestJson`.
- Never import page-specific `api.ts` from a different page's code.

---

## Flask ↔ Vite Integration

Integration is handled by `pricewatch/web/assets.py`, which exposes `vite_asset_tags(entry)` as a Jinja global.

**Dev mode** (`VITE_USE_DEV_SERVER=True`):
- Set `VITE_DEV_SERVER_URL=http://localhost:5173`.
- `vite_asset_tags('src/main.ts')` emits a `<script type="module">` tag pointing to the Vite dev server.

**Production** (`npm run build`):
- Vite writes hashed assets to `static/dist/` and a manifest to `static/dist/.vite/manifest.json`.
- `vite_asset_tags('src/main.ts')` reads the manifest and emits correct `<link>` + `<script>` tags.

**Jinja usage in `spa.html`:**
```html
{{ vite_asset_tags('src/main.ts') }}
```

---

## Static Assets Policy

| Path | Purpose |
|---|---|
| `static/css/common.css` | **Active** — shared `app-shell-*` styles loaded by `spa.html`. |
| `static/dist/` | **Generated** — Vite build output; not committed. |

---

## Testing

Frontend tests use **Vitest** and **@vue/test-utils**.

```bash
cd frontend
npm test                          # run all tests once
npm test -- --reporter=verbose    # with per-test output
npm run typecheck                 # vue-tsc --noEmit
npm run build                     # full type check + production build
```

| Test path | What it covers |
|---|---|
| `test/router/` | Router contract: canonical routes, catch-all, route meta |
| `test/api/` | `requestJson`, `ApiError`, mapping/scheduler adapters |
| `test/components/` | `AppShellHeader` (title-only), `AppShellSidebarNav` (nav contract + a11y), `AppShellLayout` (shell ownership contract) |
| `test/composables/` | Shared composables |
| `test/pages/comparison/` | Comparison page composable, `patchComparisonResult` pure helper, components |
| `test/pages/gap/` | Gap page composable and components |
| `test/pages/matches/` | Matches page composable and components |
| `test/pages/service/` | Service page tabs and components (mappings, scheduler, categories, history) |
| `test/pages/NotFoundPage.test.ts` | NotFound screen structure and path display |

---

## Guardrails

- **Flask owns `/api/*`** — never navigate to API routes from Vue components.
- **Vue Router owns UI navigation** — use `<RouterLink>` or `router.push()`, never `window.location`.
- **No inline `onclick` handlers** in `spa.html`. All interactions are Vue-owned.
- **No `window.*` global action handlers.** All interactivity is component-scoped.
- **Do not import page `api.ts` across pages.** Shared API helpers belong in `frontend/src/api/client.ts`.

---

## Mutation UX Policy

After any data mutation (confirm/reject match, gap status change, delete row):

> **Do not blank visible page content.** Keep current data on screen until the replacement arrives.

| Page | Mutation | Implementation |
|---|---|---|
| `/` (comparison) | confirm / reject | `makeDecision()` calls `applyDecisionPatch()` from `patchComparisonResult.ts` — pure helper removes acted-on pair; no comparison rerun |
| `/gap` | status change | `patchGapItemStatus()` updates item + recalculates summary locally |
| `/matches` | delete row | Row removed locally from `rows` + `total` decremented |
| `/service` → Mappings | create / update / delete | CRUD response used directly to update `mappings` list in-place; no full reload |
| `/service` → Mappings | auto-link | `POST /api/category-mappings/auto-link` returns enriched `{ summary, mappings }` in a single response — state updated atomically; no second fetch |
| `/service` → Scheduler | create job | New job appended to list; only detail for the new job is fetched |
| `/service` → Scheduler | update job | List badge + `selectedJob` patched in-place from update response; runs not touched |
| `/service` → Scheduler | upsert schedule | `selectedSchedules` patched locally from returned schedule; no full detail reload |

### Comparison patch helper

Pure patching logic lives in `frontend/src/pages/comparison/composables/patchComparisonResult.ts`.
`applyDecisionPatch(result, refProductId, tgtProductId)` returns a new `ComparisonResult` with only
the acted-on pair removed — never mutates its input. Unit-tested independently of Vue rendering in
`test/pages/comparison/patchComparisonResult.test.ts`.

