# Frontend Release Checklist

Use this checklist before merging a branch that touches `frontend/` or
`templates/spa.html`. It covers the full build → test → asset pipeline.

---

## Pre-merge checks

### 1. TypeScript passes with no errors
```bash
cd frontend && npm run typecheck
```
Expected: zero errors.

### 2. All frontend unit tests pass
```bash
cd frontend && npm test
```
Expected: all test files green, including:
- `test/router/router.test.ts` — router contract (canonical routes, catch-all, meta)
- `test/pages/NotFoundPage.test.ts` — 404 screen structure
- `test/components/AppShellHeader.test.ts` — nav structure and active-state

### 3. Production build succeeds
```bash
cd frontend && npm run build
```
Expected: `✓ built in ...` with no errors.
Output artifacts written to `static/dist/`.

### 4. All Python tests pass
```bash
SCHEDULER_ENABLED=false pytest
```
Expected: all tests pass, including:
- `tests/test_vite_assets.py` — Vite asset integration
- `tests/test_vue_page_shells.py` — SPA shell contracts

---

## Asset pipeline verification

### 5. `static/dist/` is current
After `npm run build`, verify that `static/dist/.vite/manifest.json` exists and
contains the single SPA entry key:
```
src/main.ts
```
There should be **no** `src/entries/` keys in the manifest.

### 6. No legacy JS references in `spa.html`
```bash
grep -n "static/js/" templates/spa.html
```
Expected: no output.

### 7. No inline `onclick` handlers in `spa.html`
```bash
grep -n "onclick=" templates/spa.html
```
Expected: no output.

---

## Smoke checks (manual)

Open each route and verify Vue Router navigates correctly:

| Route | URL | Expected component | Check |
|---|---|---|---|
| Comparison | `/` | `ComparisonRouteView` | Stores load, comparison executes |
| Service | `/service` | `ServiceRouteView` | Tabs render, scheduler visible |
| Gap | `/gap` | `GapRouteView` | Filters load, results render |
| Matches | `/matches` | `MatchesRouteView` | Table loads, filters work |
| Not Found | `/any/unknown/path` | `NotFoundPage` | 404 screen shown, home link works |

For each page also verify:
- No JavaScript console errors on load
- Nav link for the active page is highlighted; `/` link is NOT highlighted on `/service`, `/gap`, `/matches`
- Browser back/forward navigates correctly (scroll resets to top)
- Browser refresh on any route returns the same page (Flask catch-all serves `spa.html`)

---

## Guardrails reminders

- **Single SPA entry** — `src/main.ts` is the only registered Vite entry.
- **Vue Router owns UI navigation** — use `<RouterLink>` or `router.push()`, never `window.location`.
- **No inline `onclick`** in `spa.html`.
- **No `window.*` global action handlers**.
- **API wrappers belong in `frontend/src/pages/<page>/api.ts`** or `frontend/src/api/client.ts`.

---

## Mutation UX regression checks

After any change to composables that handle mutations:

- [ ] Confirm/reject on `/` does **not** blank comparison sections between click and response
- [ ] Gap status change updates the row and summary **without** blanking the group table
- [ ] Delete on `/matches` removes only the affected row; table stays visible
