# PriceWatch Frontend

Vue 3 + Vite 5 + TypeScript frontend for PriceWatch.

All four operator-facing pages are fully migrated to Vue.
Flask serves each page as a regular HTML response; Vue is mounted per-page
inside a single `<div id="...-app"></div>` root. There is no SPA architecture,
no Vue Router, and no Pinia.

See [`docs/frontend_architecture.md`](../docs/frontend_architecture.md) for the full
architectural rationale and conventions.

---

## Development

### Install dependencies

For local development:
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

`{{ vite_asset_tags(...) }}` in Jinja templates will then proxy assets
from the Vite dev server with hot module replacement.

### Type-check

```bash
npm run typecheck
```

### Run tests

```bash
npm test
```

### Build production bundles

```bash
npm run build
# Output: ../static/dist/
```

---

## Entry Points

All four pages are fully wired into Flask via `vite_asset_tags(...)`:

| File | Flask route | Mount root | Status |
|---|---|---|---|
| `src/entries/index.ts` | `/` | `#comparison-app` | ✅ Full implementation |
| `src/entries/service.ts` | `/service` | `#serviceApp` | ✅ Full implementation |
| `src/entries/gap.ts` | `/gap` | `#gap-app` | ✅ Full implementation |
| `src/entries/matches.ts` | `/matches` | `#matches-app` | ✅ Full implementation |

---

## Source Structure

```
src/
  entries/       ← Vite entry points (one per Flask page)
  pages/         ← Page-level components, composables, api, types
    comparison/  ← / (main comparison page)
    service/     ← /service (service console)
    gap/         ← /gap (gap review)
    matches/     ← /matches (confirmed matches)
  components/    ← Shared Vue components (BaseButton, EmptyState, StatusPill, …)
  composables/   ← Shared composables (useAsyncState, …)
  api/           ← HTTP client (http.ts), shared endpoint helpers (client.ts), adapters
  types/         ← Shared TypeScript DTO types
  styles/        ← Styles imported into Vue entry points
  test/          ← Vitest unit and component tests
```

---

## Flask Integration

Flask ↔ Vite integration is fully implemented via `pricewatch/web/assets.py`.

- `register_asset_helpers(app)` is called in `pricewatch/app_factory.py`.
- `vite_asset_tags('src/entries/<page>.ts')` is available as a Jinja global in all templates.
- Dev mode: set `VITE_USE_DEV_SERVER=True` → tags point to the running Vite dev server.
- Production mode: `npm run build` writes `static/dist/` + manifest → Flask reads manifest and emits hashed asset URLs.

---

## Global Styles

Page-specific CSS files (`index.css`, `service.css`, `gap.css`, `matches.css`) and `static/css/common.css`
are owned by Flask and included via `<link>` tags in each template.

`src/styles/base.css` is imported by Vue entry points for Vue-owned baseline styles only.

There are no legacy `static/js/` scripts remaining. All page interactivity is owned by Vue.

