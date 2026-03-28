# Frontend Release Checklist

Use this checklist before merging a branch that touches `frontend/` or any
Flask template. It covers the full build → test → asset pipeline.

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
Expected: all test files green.

### 3. Production build succeeds
```bash
cd frontend && npm run build
```
Expected: `✓ built in ...` with no errors.
Output artifacts written to `static/dist/`.

### 4. All Python tests pass (including page-shell contracts)
```bash
SCHEDULER_ENABLED=false pytest
```
Expected: all tests pass, including:
- `tests/test_vite_assets.py` — Vite asset integration
- `tests/test_vue_page_shells.py` — page shell contracts (mount roots, entry tags, no legacy JS)

---

## Asset pipeline verification

### 5. `static/dist/` is current
After `npm run build`, verify that `static/dist/.vite/manifest.json` exists and
lists all four entry points:
```
src/entries/index.ts
src/entries/service.ts
src/entries/gap.ts
src/entries/matches.ts
```

### 6. No legacy JS references in templates
```bash
grep -rn "static/js/" templates/
```
Expected: no output (no legacy script includes).

### 7. No inline `onclick` handlers in templates
```bash
grep -rn "onclick=" templates/
```
Expected: no output.

---

## Smoke checks (manual)

Open each page and verify:

| Page | URL | Vue mount root | Check |
|---|---|---|---|
| Comparison | `/` | `#comparison-app` | Stores load, comparison executes |
| Service | `/service` | `#serviceApp` | Tabs render, scheduler visible |
| Gap | `/gap` | `#gap-app` | Filters load, results render |
| Matches | `/matches` | `#matches-app` | Table loads, filters work |

For each page also verify:
- No JavaScript console errors on load
- No `window.*` global handler errors (e.g. `window.runComparison is not defined`)
- Vue DevTools shows component tree mounted

---

## Guardrail reminders

- **No Vue Router** — Flask owns routing.
- **No Pinia** — state lives in per-page composables.
- **No new `static/js/` scripts** — all interactivity must live in Vue.
- **No inline `onclick`** in any template.
- **No new dependencies on `window.*` globals**.
- **API wrappers belong in `frontend/src/pages/<page>/api.ts`** or `frontend/src/api/client.ts` — never call `fetch` directly in components.

---

## After merge

- Ensure CI (`python-app.yml`) is green on `main`:
  - Python lint + tests
  - Frontend typecheck + tests + production build
- If deploying to production: run `npm run build` in the deploy pipeline and
  ensure `static/dist/` is included in the deployment artifact.

