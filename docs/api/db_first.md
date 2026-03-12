# DB-First API

## Scope

This document describes the supported API surface for the primary user-facing flow.

These endpoints operate on persisted data and are the main product contract.

## Endpoints

### `GET /api/stores`
Returns stores from the database.

### `GET /api/stores/<store_id>/categories` *(canonical)*
Returns categories for a store from the database, including `product_count` per category.

**Path parameters:**
- `store_id` — the store's numeric identifier.

**Response:**
```json
{
  "categories": [
    {"id": 1, "name": "Ковзани", "store_id": 1, "url": "https://...", "product_count": 42}
  ]
}
```

This is the **canonical** categories endpoint. All internal consumers should use this form.
The caller is responsible for resolving the appropriate `store_id` before calling this endpoint (e.g., via `GET /api/stores`).

---

### `GET /api/categories` *(compatibility — migration target)*

> **Note:** This endpoint is a **compatibility/convenience** endpoint for the reference-store flow.
> It exists for backwards compatibility and is a **planned migration target** for deprecation
> after all internal consumers are migrated to `GET /api/stores/<store_id>/categories`.
> Do not introduce new dependencies on this endpoint.

Returns categories for the reference store, resolved automatically by the backend.
The reference store is determined by `is_reference=true` flag, falling back to the first available store.

**Deprecation headers included in response:**
- `Deprecation: true`
- `Link: </api/stores/{store_id}/categories>; rel="successor-version"`
- `Sunset: TBD — after internal consumer migration is complete`

**Response:**
```json
{
  "store": {"id": 1, "name": "RefShop", "is_reference": true},
  "categories": [
    {"id": 1, "name": "Ковзани", "store_id": 1, "product_count": 42}
  ]
}
```

---

### `GET /api/categories/<category_id>/products`
Returns products for a category from the database.

---

### `GET /api/categories/<reference_category_id>/mapped-target-categories`

Returns target categories mapped to the selected reference category.

**Query parameters:**
- `target_store_id` (optional) — filter by target store.

**Response:**
```json
{
  "reference_category": {
    "id": 1, "name": "Ковзани",
    "store_id": 1, "store_name": "RefShop", "is_reference": true
  },
  "target_store": {"id": 2, "name": "HockeyShop", "is_reference": false},
  "mapped_target_categories": [
    {
      "target_category_id": 11,
      "target_category_name": "Ключки Senior",
      "target_store_id": 2,
      "target_store_name": "HockeyShop",
      "match_type": "exact",
      "confidence": 1.0,
      "mapping_id": 5
    }
  ]
}
```

---

### `POST /api/comparison`

Builds comparison output from persisted data and mappings.

**Request:**
```json
{
  "reference_category_id": 1,
  "target_category_ids": [5, 6],
  "target_store_id": 2
}
```

Fields:
- `reference_category_id` — **required**.
- `target_category_ids` — recommended: list of mapped target category ids. Each id must exist in mappings, otherwise `400`.
- `target_category_id` — legacy fallback (single id). Ignored when `target_category_ids` is present.
- `target_store_id` — optional filter for auto-selecting target categories when `target_category_ids` is not given.

**Response:**
```json
{
  "reference_category": {"id": 1, "name": "Ковзани", "store_name": "RefShop", "is_reference": true},
  "target_store": {"id": 2, "name": "HockeyShop", "is_reference": false},
  "selected_target_categories": [
    {"target_category_id": 5, "target_category_name": "Ковзани", "match_type": "exact", "confidence": 1.0}
  ],
  "summary": {
    "confirmed_matches": 8,
    "candidate_groups": 2,
    "reference_only": 2,
    "target_only": 1
  },
  "confirmed_matches": [
    {
      "reference_product": {"id": 10, "name": "Bauer Vapor X5 SR", "price": 4500},
      "target_product": {"id": 20, "name": "Bauer Vapor X5 Senior", "price": 4800},
      "target_category": {"id": 5, "name": "Ковзани", "store_name": "HockeyShop"},
      "score_percent": 97,
      "score_details": {
        "fuzzy_base": 87.0, "token_bonus": 10.0,
        "shared_tokens": ["VAPOR", "X5"], "shared_series": ["VAPOR"],
        "domain_bonus": 16.0, "product_type": "SKATES",
        "sport_context": "ICE_HOCKEY", "total_score": 113.0
      },
      "match_source": "confirmed",
      "is_confirmed": true
    }
  ],
  "candidate_groups": [
    {
      "reference_product": {"id": 11, "name": "CCM Tacks AS-V SR"},
      "candidates": [
        {
          "target_product": {"id": 21, "name": "CCM Tacks AS-V Senior"},
          "target_category": {"id": 5, "name": "Ковзани"},
          "score_percent": 78,
          "score_details": {"fuzzy_base": 75.0, "token_bonus": 4.0},
          "match_type": "heuristic",
          "can_accept": true,
          "disabled_reason": null
        }
      ]
    }
  ],
  "reference_only": [
    {"reference_product": {"id": 12, "name": "Bauer Supreme M4 SR"}}
  ],
  "target_only": [
    {
      "target_product": {"id": 22, "name": "True Catalyst 9 Senior"},
      "target_category": {"id": 5, "name": "Ковзани"}
    }
  ]
}
```

**`confirmed_matches` fields:**
- `is_confirmed: true` — persisted `ProductMapping` in DB.
- `is_confirmed: false` — auto-high-confidence (≥ 85%) from heuristics, not yet confirmed.
- `match_source`: `"confirmed"` | `"heuristic_high_confidence"` | `"heuristic"`.

**Candidate fields:**
- `score_percent` — percentage 0–100 for UI display.
- `score_details` — detailed score breakdown for tooltip.
- `can_accept: false` + `disabled_reason: "already_confirmed_elsewhere"` — target product already used in a confirmed mapping for another reference product.

**Errors (400):**
- `reference_category_id` not found or is not a reference store.
- `target_category_id` given but pair does not exist in `category_mappings`.
- `target_category_id` not given and no mappings exist.

---

### `POST /api/comparison/confirm-match`

Persists a confirmed product match into `ProductMapping`.

**Request:**
```json
{
  "reference_product_id": 10,
  "target_product_id": 20,
  "match_status": "confirmed",
  "confidence": 0.97
}
```

**Response:** `{"product_mapping": {...}}`

After confirmation, the next comparison will show this match in `confirmed_matches` with `is_confirmed: true`.

---

### `POST /api/gap`

Returns grouped gap items for the selected review context.

**Request:**
```json
{
  "target_store_id": 2,
  "reference_category_id": 10,
  "target_category_ids": [21, 22],
  "search": "bauer",
  "only_available": true,
  "statuses": ["new", "in_progress"]
}
```

Fields:
- `target_store_id` — **required**.
- `reference_category_id` — **required**.
- `target_category_ids` — **required**, non-empty. Each id must be in mappings for `reference_category_id`, otherwise `400`.
- `search` — case-insensitive substring filter on product name.
- `only_available` — if `true`, show only products with `is_available=true`.
- `statuses` — list of visible statuses. Default: `["new", "in_progress"]`. `done` is always counted in `summary.done` regardless of this filter.

**Response:**
```json
{
  "reference_category": {"id": 10, "name": "Ключки"},
  "target_store": {"id": 2, "name": "HockeyShop"},
  "selected_target_categories": [
    {"target_category_id": 21, "target_category_name": "Ключки Senior"}
  ],
  "summary": {"total": 37, "new": 21, "in_progress": 9, "done": 7},
  "groups": [
    {
      "target_category": {"id": 21, "name": "Ключки Senior"},
      "count": 12,
      "items": [
        {
          "target_product": {
            "id": 501, "name": "Bauer Vapor X5 Pro Grip Stick Senior",
            "price": 8999, "currency": "UAH",
            "product_url": "https://...", "is_available": true
          },
          "status": "new"
        }
      ]
    }
  ]
}
```

**Errors (400):**
- `target_store_id` not given.
- `reference_category_id` not given or not found.
- `target_category_ids` empty or contains id not mapped to `reference_category_id`.

---

### `POST /api/gap/status`

Persists review status for a gap item.

**Request:**
```json
{
  "reference_category_id": 10,
  "target_product_id": 501,
  "status": "in_progress"
}
```

Accepted values for `status`: `"in_progress"`, `"done"`. Status `"new"` is **not accepted** (implicit — absence of a row in DB).

**Response:**
```json
{
  "success": true,
  "item": {
    "reference_category_id": 10,
    "target_product_id": 501,
    "status": "in_progress",
    "updated_at": "2026-03-08T10:00:00"
  }
}
```

---

## DB schema: `gap_item_statuses`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `reference_category_id` | INTEGER FK→categories | Reference category |
| `target_product_id` | INTEGER FK→products | Target product |
| `status` | VARCHAR(50) | `in_progress` or `done` |
| `created_at` | DATETIME | Creation timestamp |
| `updated_at` | DATETIME | Last update timestamp |

Unique constraint: `(reference_category_id, target_product_id)`.  
Migration: `migrations/versions/a1b2c3d4e5f6_add_gap_item_statuses.py`.
