# RFC-013: Product Match Review Workflow — Reject, Manual Selection, and Confirmed Pairs Page

- **Status:** Draft
- **Date:** 2026-03-24
- **Owners:** Project maintainers
- **Related ADRs:** ADR-0001, ADR-0002, ADR-0012

## 1. Summary

This RFC defines the implementation plan for extending the current product comparison workflow with three operator capabilities:

1. explicit rejection of an incorrect reference-target pair;
2. manual target-product selection from the currently selected target categories;
3. a dedicated page for browsing persisted confirmed product mappings.

The implementation must fit the current repository structure and runtime model:

- Flask backend;
- server-rendered HTML templates;
- vanilla JavaScript frontend;
- SQLAlchemy persistence;
- DB-first comparison semantics.

## 2. Goals

This RFC aims to:

1. let operators reject a specific false-positive pair even when heuristic confidence is very high;
2. ensure rejected pairs do not reappear in later comparison results;
3. let operators confirm a match by selecting any eligible target product from the active target-category scope, not only from the heuristic shortlist;
4. add a dedicated operator-facing page for reviewing confirmed persisted mappings;
5. preserve the current confirmed-mapping cardinality rule in this wave;
6. keep persisted positive truth limited to `match_status="confirmed"`.

## 3. Non-Goals

This RFC does not:

1. introduce full audit history for all decision transitions;
2. allow manual product search across the entire target store;
3. introduce bulk confirm/reject operations;
4. redesign the comparison page into a SPA framework;
5. change confirmed mapping cardinality semantics;
6. introduce background candidate precomputation.

## 4. Confirmed decisions captured by this RFC

The following product and architecture decisions are already resolved and are not open questions for this RFC:

1. reject is a durable **pair-level** decision;
2. confirm may override an earlier reject for the same exact pair;
3. manual searchable selection is bounded to the **currently selected target categories**;
4. the current **one target product cannot be confirmed for multiple reference products** rule remains in force in this wave;
5. the confirmed-pairs page is **read-only** in the first iteration;
6. only `confirmed` remains authoritative persisted truth.

## 5. Current repository fit

### Primary backend touch points

- `pricewatch/services/comparison_service.py`
- `pricewatch/web/admin_comparison_gap_routes.py`
- `pricewatch/db/repositories/mapping_repository.py`
- `pricewatch/schemas/requests/comparison.py`
- `pricewatch/web/serializers.py`

### Primary frontend touch points

- `templates/index.html`
- `static/js/index.js`
- `static/css/index.css`
- UI route registration under `pricewatch/web/*`
- new template for confirmed mappings page

### Existing observed behavior to preserve or correct

- `ProductMapping.match_status` already exists;
- current comparison logic relies on persisted `confirmed` mappings as authoritative truth;
- current comparison UI can persist a confirmed pair through `/api/comparison/confirm-match`;
- high-confidence heuristic suggestions are currently surfaced close to confirmed results, which creates semantic ambiguity and must be clarified in UI and, preferably, in API shape.

## 6. Domain semantics

## 6.1 Supported statuses in this wave

This workflow explicitly supports:

- `confirmed`
- `rejected`

### `confirmed`

Meaning:

- authoritative persisted positive mapping;
- appears on the confirmed-pairs page;
- participates in comparison as persisted truth;
- blocks reuse of the same target product elsewhere if the current uniqueness-style invariant would be violated.

### `rejected`

Meaning:

- durable negative review decision for one exact pair;
- suppresses that pair from future comparison output;
- does not count as positive truth;
- does not globally blacklist the target product for other reference products.

## 6.2 Decision override semantics

If the exact pair already exists in `ProductMapping`, a new explicit operator decision updates that same pair state.

Examples:

- `rejected -> confirmed` is allowed;
- `confirmed -> rejected` is allowed.

The persisted current state for the pair is the latest explicit operator decision.

## 6.3 Manual target selection semantics

For a given reference product under review, the searchable selector may offer any target product that satisfies all of the following:

1. belongs to one of the currently selected target categories;
2. is not already confirmed elsewhere in a way that would violate current mapping invariants;
3. is not hidden by the exact pair already being rejected, unless the operator is intentionally choosing that exact row to change the prior decision.

## 7. API changes

## 7.1 New match-decision endpoint

The current endpoint name is too narrow:

- `POST /api/comparison/confirm-match`

The comparison review model should move to:

- `POST /api/comparison/match-decision`

### Request body

```json
{
  "reference_product_id": 123,
  "target_product_id": 456,
  "match_status": "confirmed",
  "confidence": 0.93,
  "comment": "optional operator note",
  "target_category_ids": [77, 78]
}
```

### Accepted values

- `match_status`: `confirmed | rejected`
- `confidence`: optional numeric value
- `comment`: optional text value
- `target_category_ids`: optional list of integers.  When provided for a
  `confirmed` decision, the server validates that the chosen target product
  belongs to one of the supplied categories and that each category is a valid
  mapped target for the reference product's category (scope guard).
  Old callers that omit this field continue to work (backward-compatible).

### Server-side invariants (enforced since fixup series)

- A target product may not be `confirmed` for more than one reference product
  simultaneously.  Attempting to do so returns `HTTP 409` with:
  ```json
  {
    "error": "target product is already confirmed for another reference product",
    "conflicting_reference_product_id": 99
  }
  ```
- When `target_category_ids` is supplied, the target product's actual category
  must be in that list; otherwise `HTTP 400` is returned.

### Compatibility strategy

The old endpoint may remain temporarily as a compatibility shim that internally calls the same handler with `match_status="confirmed"`.

## 7.2 Eligible target-products endpoint

The manual selector requires a scoped searchable list of eligible target products.

### Proposed endpoint

- `GET /api/comparison/eligible-target-products`

### Query parameters

- `reference_product_id` — required for pair-level suppression and uniqueness checks
- `target_category_ids[]` — required
- `search` — optional text filter
- `limit` — optional, default small page size
- `include_rejected` — optional boolean (`true`/`false`), default `false`.
  When `true`, previously rejected pairs for this reference product are
  re-included in results.  Globally confirmed targets are always excluded
  regardless of this flag.

### Response shape

```json
{
  "products": [
    {
      "id": 456,
      "name": "Target product name",
      "store_id": 8,
      "category_id": 77,
      "category": { "id": 77, "name": "Category name", "store_name": "Shop" },
      "price": 8999.0,
      "currency": "UAH",
      "product_url": "https://..."
    }
  ]
}
```

## 7.3 Confirmed mappings list endpoint

### Proposed endpoint

- `GET /api/product-mappings`

### Initial filters

- `reference_store_id`
- `target_store_id`
- `reference_category_id`
- `target_category_id`
- `status` with default `confirmed`
- `search`

### Response content

Each row should include enough information for a useful review table:

- mapping id;
- reference product id and name;
- target product id and name;
- reference category id and name;
- target category id and name;
- status;
- confidence;
- comment;
- created/updated timestamps where available.

## 8. Backend design

## 8.1 Request DTOs

Introduce a new request DTO representing a generic match decision:

- `reference_product_id: int`
- `target_product_id: int`
- `match_status: Literal["confirmed", "rejected"]`
- `confidence: Optional[float]`
- `comment: Optional[str]`

The current confirm-only DTO may remain temporarily for compatibility while the frontend is migrated.

## 8.2 Repository responsibilities

`mapping_repository.py` should expose explicit helpers for:

1. create-or-update decision for an exact pair;
2. list persisted mappings with filters for the review page;
3. query rejected pairs relevant to comparison suppression;
4. check whether a target product is already confirmed elsewhere.

The exact helper names are implementation detail, but the service layer should avoid ad hoc repeated decision lookups.

## 8.3 ComparisonService changes

### 8.3.1 Use `rejected` as pair-level suppression input

Before building runtime suggestions, the comparison service must exclude any exact pair already marked `rejected`.

This applies to:

- high-confidence suggestions;
- heuristic candidate groups;
- eligible-target search results for manual selection.

### 8.3.2 Preserve confirmed mappings as authoritative truth

Stored confirmed mappings continue to be shown as persisted positive results and remain separate in semantics from runtime-only suggestions.

### 8.3.3 Reclassify reference products when suppression removes the only visible candidate

If suppression removes the last remaining candidate for a reference product, that reference product may now appear under `reference_only`.

### 8.3.4 Clarify response semantics for high-confidence heuristic rows

The current API shape mixes persisted confirmed mappings and high-confidence heuristic suggestions too closely.

This RFC recommends a staged clarification:

#### Target response shape

Prefer separate payload sections:

- `persisted_matches`
- `auto_high_confidence_matches`
- `candidate_groups`
- `reference_only`
- `target_only`

#### Transitional strategy

If immediate payload splitting is too disruptive, keep backward compatibility temporarily but ensure the frontend renders persisted and runtime suggestions as distinct sections with explicit badges and labels.

## 9. Frontend design

## 9.1 Comparison page actions

The comparison page must support all of the following:

1. confirm a high-confidence auto suggestion;
2. reject a high-confidence auto suggestion;
3. confirm a candidate from the heuristic shortlist;
4. reject a candidate from the heuristic shortlist;
5. search and confirm another eligible target product from the selected target categories.

## 9.2 Manual selector behavior

Each candidate-review block should include a searchable dropdown or combobox that:

- loads from `GET /api/comparison/eligible-target-products`;
- filters by the currently selected target categories;
- supports text search;
- shows enough context to distinguish options, including category name and price when available;
- disables or omits non-eligible rows according to the chosen response strategy.

A selected manual target can then be submitted through the match-decision endpoint with `match_status="confirmed"`.

## 9.3 Clear visual distinction between persisted and runtime suggestions

The page must not visually imply that an auto-high-confidence heuristic pair is already persisted.

At minimum, the UI must distinguish:

- persisted confirmed mapping;
- auto suggestion awaiting operator action;
- candidate list awaiting operator action.

## 9.4 New confirmed mappings page

### Route

A dedicated UI route should be added, for example:

- `/matches`

### Initial capabilities

The page is read-only in this wave and should provide:

- table view of confirmed mappings;
- filters by store/category/status;
- simple text search;
- links to reference and target product URLs when available.

## 10. Validation and business rules

The implementation must enforce the following rules:

1. only supported statuses may be accepted by the decision endpoint;
2. a `confirmed` decision must be rejected if it would violate the current one-target-per-confirmed-pair invariant;
3. a `rejected` decision must be allowed for any exact persisted or runtime-visible pair in scope;
4. manual selection must stay within the currently selected target categories;
5. comparison output must not resurface a previously rejected pair unless the operator is intentionally viewing or changing that exact persisted pair elsewhere.

## 11. Testing requirements

At minimum, add tests for:

1. rejecting a high-confidence suggestion suppresses the exact pair from later comparison runs;
2. rejecting a shortlist candidate suppresses the exact pair from later comparison runs;
3. a later confirm for the same pair overrides an earlier reject;
4. a later reject for the same pair overrides an earlier confirm;
5. eligible-target lookup excludes rows already confirmed elsewhere when current invariants require that;
6. eligible-target lookup is limited to selected target categories;
7. confirmed mappings list endpoint returns filtered persisted rows correctly;
8. comparison payload or UI rendering clearly separates persisted matches from runtime suggestions.

## 12. Rollout plan

### Phase 1 — backend decision semantics

- add decision DTO and decision handler;
- add repository helpers;
- teach comparison service to honor rejected-pair suppression.

### Phase 2 — comparison UI controls

- add reject buttons to auto suggestions and candidate shortlist rows;
- add manual searchable target selector;
- visually separate persisted matches from runtime suggestions.

### Phase 3 — confirmed mappings page

- add list API;
- add read-only UI table with filters and search.

### Phase 4 — cleanup

- optionally migrate the frontend fully from confirm-only endpoint naming to generic match-decision naming;
- retire compatibility shims when no longer needed.

## 13. Risks

### Risk 1: semantic confusion between auto suggestions and persisted matches

Mitigation: explicit API naming and distinct UI sections/badges.

### Risk 2: manual selector becomes too broad or slow

Mitigation: keep it limited to selected target categories and page the search results conservatively.

### Risk 3: inconsistent enforcement of current mapping uniqueness rule

Mitigation: centralize the check in service/repository logic used by both heuristic and manual confirmation paths.

## 14. Deferred follow-ups

The following topics are explicitly deferred and are not blockers for this RFC:

1. write actions on the confirmed mappings page, such as unconfirm or delete;
2. richer decision history and audit logging;
3. global target-store search outside the selected target categories;
4. bulk decision workflows.

## 15. Acceptance criteria

This RFC is satisfied when all of the following are true:

1. operators can reject an incorrect exact pair from the comparison page;
2. rejected pairs do not reappear during later comparison;
3. operators can manually confirm an eligible target product from the selected target categories;
4. the UI clearly separates persisted confirmed mappings from runtime heuristic suggestions;
5. a dedicated read-only confirmed mappings page exists and is backed by a list API;
6. current confirmed mapping invariants remain enforced.
