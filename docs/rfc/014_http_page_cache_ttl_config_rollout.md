# RFC-014: HTTP Page Cache TTL Config Rollout

- Status: Accepted for implementation
- Date: 2026-03-24
- Owners: Project maintainers
- Related ADRs: ADR-0013

## 1. Summary

This RFC defines a narrow rollout for changing scraper HTTP page-cache freshness from a day-based setting to a second-based setting and changing the default cached-page lifetime from 30 days to 5 minutes.

The primary scope is the scraper network client.

A small adjacent optimization may be implemented in the same patch train: push down `ComparisonService.get_eligible_target_products()` filtering to SQL so that large-category manual picker queries do not load all products into Python first. That optimization is an implementation improvement, not a public contract change.

## 2. Goals

This RFC aims to:

1. introduce `PARSER_CACHE_TTL_SECONDS` as the canonical page-cache TTL setting;
2. set the default TTL to `300` seconds;
3. migrate `HttpClient` freshness semantics from days to seconds;
4. preserve temporary backward compatibility with `PARSER_CACHE_MAX_AGE_DAYS`;
5. update tests and docs so the new behavior is explicit.

## 3. Non-goals

This RFC does not:

1. redesign the HTTP client lifecycle;
2. replace the module-level `default_client` pattern;
3. change cache file naming or storage layout;
4. add cache invalidation endpoints or UI controls;
5. change Flask response cache headers.

## 4. Current repository fit

### Primary touch points

- `pricewatch/net/http_client.py`
- `pricewatch/net/__init__.py`
- `.env.example`
- operator/runtime docs if they mention cache configuration
- tests:
  - `tests/test_cache.py`
  - `tests/test_http_client.py`
  - `tests/test_http_client_decoding.py`
  - `tests/test_utils.py`

### Current behavior

- `HttpClient.__init__()` accepts `cache_max_age_days`;
- `_is_cache_valid()` converts days to seconds;
- `make_default_client()` reads:
  - `PARSER_CACHE_DIR`
  - `PARSER_CACHE_MAX_AGE_DAYS`
  - `PARSER_FAST`
- the import-time `default_client` uses those environment-derived values.

## 5. Accepted design

### 5.1 Canonical config contract

Introduce canonical cache TTL config:

- `PARSER_CACHE_TTL_SECONDS`

Default:

- `300`

Temporary fallback:

- `PARSER_CACHE_MAX_AGE_DAYS`

Resolution order:

1. `PARSER_CACHE_TTL_SECONDS`
2. `PARSER_CACHE_MAX_AGE_DAYS * 86400`
3. `300`

### 5.2 `HttpClient` API update

`HttpClient` moves from:

- `cache_max_age_days`

to:

- `cache_ttl_seconds`

Affected behavior:

- constructor argument name;
- instance attribute name;
- cache-validity calculation;
- test fixtures/helpers.

The cache-validity rule becomes:

```python
file_age_seconds < cache_ttl_seconds
```

### 5.3 `make_default_client()` behavior

`make_default_client()` should:

1. continue reading `PARSER_CACHE_DIR` and `PARSER_FAST` as today;
2. read `PARSER_CACHE_TTL_SECONDS` first;
3. fall back to `PARSER_CACHE_MAX_AGE_DAYS` converted to seconds;
4. fall back to `300` if neither is set.

This rollout keeps environment-based default-client construction as the operational source of truth.

### 5.4 Documentation update

The repository should document the new setting in at least:

- `.env.example`
- one operator-facing location if runtime config variables are documented there

If `PARSER_CACHE_MAX_AGE_DAYS` is mentioned, it should be explicitly marked as deprecated.

## 6. Adjacent optimization bundled into the implementation wave

### 6.1 Problem

`ComparisonService.get_eligible_target_products()` currently loads every product from each requested target category via repeated `list_products_by_category()` calls and then applies:

- name filtering;
- rejection filtering;
- confirmed-elsewhere filtering;
- result limiting;

partly in Python.

This is inefficient for large categories.

### 6.2 Accepted implementation direction

In the same implementation wave, it is acceptable to replace the current multi-query + Python-filter approach with a repository-level SQL query that:

- filters by `Product.category_id IN (...)`;
- applies optional name filtering at the DB level;
- excludes globally confirmed target products;
- excludes exact rejected pairs for the given reference product when `include_rejected=False`;
- eager-loads or joins `Category` so current response serialization can remain intact;
- applies deterministic ordering and `limit` at the DB level.

This optimization must preserve current API behavior and response shape.

### 6.3 Scope boundary

This optimization is **implementation-only**:

- no new ADR is required;
- no API contract changes are intended;
- the goal is reduced database and Python work for large manual-picker requests.

## 7. Implementation plan

### 7.1 Cache TTL changes

In `pricewatch/net/http_client.py`:

1. rename the constructor argument to `cache_ttl_seconds`;
2. rename the instance field accordingly;
3. update `_is_cache_valid()` to compare directly against seconds;
4. add helper logic that resolves the effective TTL using the accepted precedence order;
5. update `make_default_client()` to use that helper;
6. keep `default_client = make_default_client()`.

### 7.2 Test updates for cache TTL

Update all tests and helpers that instantiate `HttpClient`.

Examples:

- `tests/test_utils.py` should construct clients with `cache_ttl_seconds=...`;
- `tests/test_cache.py` should simulate expired cache using second-based TTL math;
- `tests/test_http_client.py` and `tests/test_http_client_decoding.py` should stop using `cache_max_age_days`.

Add focused tests for:

- precedence: `PARSER_CACHE_TTL_SECONDS` wins over `PARSER_CACHE_MAX_AGE_DAYS`;
- fallback: absent config resolves to `300`.

### 7.3 Query optimization for eligible target products

Introduce a repository-level helper in `pricewatch/db/repositories/product_repository.py` (name to be chosen by implementer, but it must clearly describe category-scoped eligible-product search) and update `ComparisonService.get_eligible_target_products()` to use it.

The helper should:

- accept `category_ids`, `search`, `limit`, `reference_product_id`, and `include_rejected` inputs as needed;
- apply the core filtering in SQL;
- return `Product` rows with category data available for current serializer usage.

### 7.4 Behavioral guardrails for the optimization

The optimization must not change these outcomes:

- off-scope categories still fail validation before query execution;
- already-confirmed-elsewhere targets are excluded;
- rejected exact pairs stay excluded unless `include_rejected=True`;
- returned items still include serialized category metadata;
- current endpoint response shape stays unchanged.

## 8. Resolved review points

### Q1. Do we migrate client wiring to `app.config` in this wave?

Resolved: **No**.

### Q2. Do we keep a deprecated fallback for `PARSER_CACHE_MAX_AGE_DAYS`?

Resolved: **Yes**.

### Q3. Do we rename internal references to seconds-based naming now?

Resolved: **Yes**.

### Q4. Is startup logging of effective TTL required?

Resolved: **No** for this wave. Optional later.

## 9. Risks

1. a partial rename may leave helper factories or tests using the old constructor argument;
2. an accidental expansion into broader client-lifecycle refactoring would create unnecessary churn;
3. a careless DB-query rewrite for eligible target products could accidentally change filtering semantics or response shape.

## 10. Acceptance criteria

This RFC is considered implemented when:

1. `HttpClient` uses second-based TTL naming and logic;
2. default effective TTL is `300` seconds;
3. `PARSER_CACHE_TTL_SECONDS` is the canonical setting;
4. `PARSER_CACHE_MAX_AGE_DAYS` still works as a deprecated fallback;
5. tests are updated and green;
6. docs/examples mention the new setting;
7. `get_eligible_target_products()` no longer loads all products per category and then applies search/limit in Python.
