# ADR-0013: Configurable HTTP Page Cache TTL for Scraper Requests

- Status: Accepted
- Date: 2026-03-24
- Related: ADR-0001 DB-first architecture; ADR-0010 production runtime topology; RFC-014 HTTP page cache TTL config rollout

## Context

The scraper network layer caches fetched HTTP pages on disk in `pricewatch/net/http_client.py`.

In the current repository state:

- `HttpClient` stores cache freshness as `cache_max_age_days`;
- `_is_cache_valid()` converts this value to seconds internally;
- `make_default_client()` reads `PARSER_CACHE_MAX_AGE_DAYS` from the environment;
- the fallback default is `30` days;
- a module-level `default_client = make_default_client()` is created at import time and is used by sync services and adapter-facing routes.

The requested change is to make the HTTP page-cache lifetime configurable and to set the default cached-page lifetime to **5 minutes**.

This ADR applies only to the scraper page cache used by the network client. It does **not** describe Flask response caching or HTTP cache-control headers returned by the web application.

## Decision

### 1. The canonical cache TTL setting is `PARSER_CACHE_TTL_SECONDS`

The canonical public configuration key for cached scraper-page freshness is:

- `PARSER_CACHE_TTL_SECONDS`

This value controls how long a cached GET response remains eligible for reuse.

### 2. The canonical unit is seconds

The public configuration contract and the internal `HttpClient` freshness semantics move from day-based naming to second-based naming.

The internal field should become:

- `cache_ttl_seconds`

The cache validity rule becomes a direct second-based comparison.

### 3. The default TTL is 300 seconds

If no explicit configuration is provided, the effective cached-page TTL is:

- `300` seconds
- i.e. **5 minutes**

### 4. `PARSER_CACHE_MAX_AGE_DAYS` remains as a temporary deprecated fallback

The legacy setting:

- `PARSER_CACHE_MAX_AGE_DAYS`

remains supported in this rollout wave only as a compatibility fallback.

Resolution order:

1. `PARSER_CACHE_TTL_SECONDS`
2. `PARSER_CACHE_MAX_AGE_DAYS` converted to seconds
3. default `300`

### 5. This wave does not refactor the default-client lifecycle

The repository currently exposes a module-level `default_client` created at import time.

This ADR does **not** require replacing that pattern with app-scoped wiring, dependency injection, or per-request client creation.

The accepted scope is intentionally narrow:

- update the config contract;
- update `HttpClient` internals to use seconds;
- keep the current `default_client` construction model.

## Rationale

### Why seconds

The requested default is 5 minutes. Representing that directly in seconds is simpler, clearer, and less error-prone than keeping a day-based public contract and converting indirectly.

### Why keep a compatibility fallback

Existing local environments, scripts, and CI shells may still set `PARSER_CACHE_MAX_AGE_DAYS`. Preserving a deprecated fallback avoids unnecessary breakage while the repository converges on one canonical key.

### Why avoid a broader config-wiring refactor now

The current repository imports `default_client` directly from multiple services and routes. Replacing that pattern would broaden this follow-up into client-lifecycle and app-wiring work unrelated to the TTL requirement itself.

## Consequences

### Positive

- cached-page freshness becomes precise and understandable;
- the default behavior becomes aligned with an active scraping workflow;
- operators can tune page-cache freshness without editing code;
- code semantics and config semantics become consistent.

### Negative

- tests and helper factories that still assume day-based naming must be updated;
- the codebase temporarily supports both the canonical key and the deprecated fallback;
- the global import-time `default_client` lifecycle remains in place for now.

## Operational implications

- default scraper page-cache freshness becomes **5 minutes**;
- environments that still use `PARSER_CACHE_MAX_AGE_DAYS` continue to work during the compatibility window;
- `.env.example` and operator-facing docs should describe `PARSER_CACHE_TTL_SECONDS` as the preferred setting.

## Non-goals

This ADR does not:

- change Flask response cache headers;
- redesign cache file storage or filenames;
- add cache invalidation endpoints or UI controls;
- replace `default_client` with request-scoped client creation;
- introduce per-store or per-adapter TTL policy.

## Alternatives considered

### Keep a day-based public config and convert 5 minutes indirectly

Rejected because it keeps the public contract misleading and awkward.

### Remove compatibility and break old environments immediately

Rejected for this rollout wave because the change is operational and does not justify forced breakage.

### Refactor to `app.config` / injected client construction now

Rejected for this wave because it expands scope into a runtime lifecycle refactor.

## Resolved review points

### Canonical unit

Accepted: **seconds**.

### Backward compatibility

Accepted: keep `PARSER_CACHE_MAX_AGE_DAYS` as a **deprecated fallback** for this rollout wave.

### `app.config` wiring in this change

Accepted: **do not** pull this change into a broader app-wiring refactor.

### Internal rename

Accepted: rename internal fields and constructor arguments to second-based naming now.

### Startup logging of effective TTL

Accepted position: optional follow-up, **not** required for this implementation.

## Review trigger

Revisit this ADR if any of the following becomes true:

- the project replaces the module-level `default_client` pattern;
- cache policy must differ by store or adapter;
- the compatibility fallback is ready to be removed.
