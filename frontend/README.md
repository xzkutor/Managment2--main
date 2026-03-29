# PriceWatch Frontend

Vue 3 + Vite 5 + TypeScript SPA frontend for PriceWatch.

All four operator-facing pages are served through a single SPA shell (`spa.html`).
Flask owns the backend API (`/api/*`) and serves `spa.html` for all UI routes.
Vue Router owns client-side navigation. Pinia is available for cross-component state.

See [`docs/frontend_architecture.md`](../docs/frontend_architecture.md) for the full
architectural rationale and conventions.

---

## Development

### Install dependencies

```bash
npm install
```

For CI and reproducible installs use the lockfile:
```bash
npm ci
```

### Start Vite dev server (with Flask)

Run Flask and Vite simultaneously:
```bash
# Terminal 1 — Flask backend
cd ..
python app.py

# Terminal 2 — Vite dev server
npm run dev
```

Set these in your Flask config (or `.env`):
```
VITE_USE_DEV_SERVER=True
VITE_DEV_SERVER_URL=http://localhost:5173
```

`{{ vite_asset_tags('src/main.ts') }}` in `spa.html` will then proxy assets
from the Vite dev server with hot module replacement.

### Type-check

```bash
npm run typecheck
```

### Run tests

```bash
npm test
```

### Build production bundle

```bash
npm run build
# Output: ../static/dist/
```

---

## SPA Entry Point

There is one Vite entry point:

| File | Flask serves | Loaded by |
|---|---|---|
| `src/main.ts` | `spa.html` for all UI routes | `{{ vite_asset_tags('src/main.ts') }}` in `spa.html` |

`src/main.ts` mounts the root `App.vue` component, registers `vue-router` and `pinia`,
and hands routing to `AppShellLayout` → `RouterView`.

---

## Routing

Vue Router (`src/router/`) owns all client-side navigation in history mode:

| Path | Route name | Page component |
|---|---|---|
| `/` | `comparison` | `ComparisonRouteView.vue` |
| `/service` | `service` | `ServiceRouteView.vue` |
| `/gap` | `gap` | `GapRouteView.vue` |
| `/matches` | `matches` | `MatchesRouteView.vue` |
| `/:pathMatch(.*)*` | `not-found` | `NotFoundPage.vue` |

Flask's `ui_routes.py` catch-all returns `spa.html` for any unknown non-`/api/` path,
so browser refreshes and deep links always land in the SPA correctly.

---

## Source Structure

```
src/
  main.ts          ← Single SPA entry point
  App.vue          ← Root component (mounts AppShellLayout)
  router/          ← Vue Router instance and route table
  layouts/         ← AppShellLayout.vue (left sidebar + content + RouterView)
  components/      ← Shared Vue components:
                      AppShellSidebarNav — canonical app navigation (left sidebar)
                      AppShellHeader — page title/subtitle only (no nav links)
                      BaseButton, EmptyState, StatusPill, …
  constants/       ← Shared constants (navigation.ts — canonical nav link list)
  composables/     ← Shared composables (useAsyncState, …)
  pages/           ← Page-level components, composables, api, types
    comparison/    ← / (main comparison page)
    service/       ← /service (service console)
    gap/           ← /gap (gap review)
    matches/       ← /matches (confirmed matches)
    NotFoundPage.vue ← Client-side 404
  api/             ← HTTP client (http.ts), shared endpoint helpers (client.ts), adapters
  stores/          ← Pinia stores (if any)
  types/           ← Shared TypeScript DTO types
  styles/          ← Styles imported by main.ts
  test/            ← Vitest unit and component tests
    router/        ← Router contract tests
    components/    ← Component tests (AppShellHeader, AppShellSidebarNav, …)
    composables/   ← Composable tests
    pages/         ← Page-level tests
    api/           ← API layer tests
```

---

## Flask Integration

Flask ↔ Vite integration is handled by `pricewatch/web/assets.py`.

- `register_asset_helpers(app)` is called in `pricewatch/app_factory.py`.
- `vite_asset_tags('src/main.ts')` is available as a Jinja global in all templates.
- Dev mode: `VITE_USE_DEV_SERVER=True` → tags point to the running Vite dev server.
- Production: `npm run build` writes `static/dist/` + manifest → Flask reads manifest and emits hashed asset URLs.

---

## Global Styles

`static/css/common.css` (loaded by `spa.html`) provides all `app-shell-*` CSS classes.
`src/styles/base.css` is imported by `main.ts` for Vue-owned baseline styles.
