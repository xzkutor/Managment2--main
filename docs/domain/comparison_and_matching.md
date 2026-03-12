# Comparison and Matching

## Purpose

This document defines how comparison works and how matching results are interpreted.

## High-level model

Comparison is built around a reference catalog and one or more mapped target categories.

The system produces four conceptual result classes:

1. confirmed matches
2. candidate groups
3. reference-only items
4. target-only items

## Confirmed matches

Confirmed matches are backed by persisted `ProductMapping` records.

Rules:
- they are treated as trusted matches
- they must appear consistently across repeated comparisons until data changes invalidate them
- confirmation is an explicit action, not an automatic side effect of candidate generation
- `is_confirmed: true` — persisted `ProductMapping` in DB
- `is_confirmed: false` — auto-high-confidence (≥ 85 %) from heuristics, not yet manually confirmed
- `match_source`: `"confirmed"` | `"heuristic_high_confidence"` | `"heuristic"`

## Candidate groups

Candidate groups are runtime-only heuristic results.

Rules:
- they are not persisted as truth
- they may include confidence/reasoning metadata (`score_details`)
- they are inputs for human review and later confirmation
- they may disappear or change after product data refresh or heuristic changes
- `can_accept: false` + `disabled_reason: "already_confirmed_elsewhere"` — target product already used in another confirmed mapping

## Reference-only items

These are products from the selected reference category scope that have:
- no confirmed mapping
- no acceptable candidate in the selected target scope

## Target-only items

These are products from the selected target category scope that have:
- no confirmed mapping
- no candidate relation to reference products in the selected context

Important:
target-only in comparison output and "gap" in `/gap` are related but not identical concepts.
Gap is a review workflow built on top of target-only logic plus status tracking and context filtering.

## Matching policy

The current project uses domain-oriented heuristics for sports/hockey catalog matching.

At a policy level:
- product type mismatch is a hard negative
- incompatible sports context is a hard negative or a major penalty
- goalie markers, handedness, curve, fit profile and similar domain tokens influence scoring
- normalized text is necessary but not sufficient for a good match

## Persistence policy

Persist:
- confirmed `ProductMapping`

Do not persist as business truth:
- transient candidates
- temporary ranking lists
- ad hoc debugging parse results

## Failure and fallback policy

When mappings do not exist:
- comparison must not proceed as a normal successful flow
- UI should prompt the user to go to `/service`
- API should return a validation error rather than guessing

When data is stale:
- keep the DB-first contract
- direct the user to refresh data operationally
- do not silently replace the contract with live scrape behavior

# Heuristic matching algorithm

The matching heuristic (`heuristic_match` in `pricewatch/core/normalize.py`) uses domain dictionaries, deterministic extractors and a multi-level system of hard blocks / penalties / bonuses.

## Scoring pipeline (`_pair_score`)

| Step | Check | Action |
|---|---|---|
| 1 | **Hard brand block** | Both brands known and different → `-1e9` |
| 2 | **Sport context conflict** | ICE_HOCKEY ↔ INLINE_HOCKEY ↔ FLOORBALL → `-1e9` |
| 3 | **Goalie conflict** | One product goalie, other not → `-1e9` |
| 4 | **Product type conflict** | Incompatible types (STICK ↔ SKATES, GLOVES ↔ HELMET…) → `-1e9` |
| 5 | **Accessory conflict** | Accessory vs main equipment → `-1e9` |
| 6 | **Fuzzy base** | `fuzz.token_set_ratio` (0–100) |
| 7 | **Token bonus** | Numeric tokens (X5, FT6, P28…) `+10`; alpha series `+4` |
| 8 | **Penalties** | flex `-40`, hand `-60`, level `-25`, curve `-20`, skate fit `-30`, size `-15` |
| 9 | **Bonuses** | product_type `+5`, sport_context `+3`, goalie `+4`, series `+8`, curve `+6`, hand `+5`, flex `+4`, skate_fit `+6` |
| 10 | **Price modifier** | ±3/5 pts (never blocks a match) |

## Score thresholds

| Constant | Value | Role |
|---|---|---|
| `MIN_CANDIDATE_SCORE` | 65 | Minimum to appear as a candidate |
| `HIGH_CONFIDENCE_SCORE` | 85 | Auto-include in `confirmed_matches` |
| `MIN_GAP` | 6 | Minimum gap between 1st and 2nd candidate |

## `score_details` full structure

```json
{
  "fuzzy_base": 87.0,
  "token_bonus": 20.0,
  "shared_tokens": ["FT6PRO", "JETSPEED", "P28"],
  "shared_series": ["JETSPEED"],
  "domain_bonus": 26.0,
  "product_type": "STICK",
  "sport_context": "ICE_HOCKEY",
  "brand_conflict": "BAUER vs CCM",
  "product_type_conflict": "STICK vs SKATES",
  "sport_context_conflict": "ICE_HOCKEY vs INLINE_HOCKEY",
  "goalie_conflict": "goalie=True vs goalie=False",
  "accessory_conflict": "accessory=True vs accessory=False",
  "level_conflict": "SR vs JR",
  "flex_conflict": "77 vs 102",
  "hand_conflict": "L vs R",
  "curve_conflict": "P28 vs P92",
  "skate_fit_conflict": "FIT1 vs FIT3",
  "size_conflict": "['9.5'] vs ['10.0']",
  "price_mod": 3.0,
  "price_ratio": 0.94,
  "total_score": 113.0
}
```

---

## Domain dictionaries

### Product types — 21 types

| Player | Goalie |
|---|---|
| STICK, SKATES, GLOVES | GOALIE_STICK, GOALIE_SKATES, GOALIE_GLOVE, GOALIE_BLOCKER |
| SHIN_GUARDS, ELBOW_PADS, SHOULDER_PADS | GOALIE_PADS, GOALIE_CHEST, GOALIE_PANTS, GOALIE_HELMET |
| HELMET, PANTS, NECK_GUARD, JOCK_JILL, WRIST_GUARD | — |
| BAG, ACCESSORY | — |

Notes:
- `ACCESSORY` / `BAG` classification applied **only** if an accessory context token is present (laces/tape/bag/etc.) **and** no main equipment token (stick/skat/glove/etc.) is present.
- Goalie modifiers (goalie/воротар/вратар) automatically convert STICK→GOALIE_STICK, SKATES→GOALIE_SKATES, etc.

### Model series (`MODEL_SERIES` + `_COMPOUND_SERIES`)

| Single | Compound (normalised to token) |
|---|---|
| VAPOR, SUPREME, NEXUS, HYPERLITE, MACH, SHADOW | SUPERTACKS (Super Tacks) |
| JETSPEED, TACKS, RIBCOR, CATALYST, HZRDUS | FT6PRO, FT4PRO, M5PRO, M50PRO |
| MISSION, TOUR, PRODIGY, ELITE, VIZION, GSX | X5PRO, X4PRO, 3XPRO, 3SPRO |
| GRIPTAC, POWERFLY | ASV (AS-V), FLYTI (Fly-Ti) |

### Curve tokens (`CURVE_TOKENS`)
P28, P29, P88, P90TM, P92, P30, P31, P40, P46.

### Skate fit tokens (`SKATE_FIT_TOKENS`)
FIT1, FIT2, FIT3, D, EE (wide→EE, regular→D).

### Sport context
ICE_HOCKEY / INLINE_HOCKEY / FLOORBALL.

---

## Extractors

| Function | Returns |
|---|---|
| `_extract_product_type(title)` | Canonical type or `None` |
| `_extract_sport_context(title)` | `ICE_HOCKEY` / `INLINE_HOCKEY` / `FLOORBALL` / `None` |
| `_extract_goalie_flag(title)` | `bool` |
| `_extract_curve(title)` | `P28`, `P92`, `P90TM`… or `None` |
| `_extract_skate_fit(title)` | `FIT1`/`FIT2`/`FIT3`/`D`/`EE` or `None` |
| `_extract_numeric_size_tokens(title)` | `tuple` of numeric sizes |
| `_extract_accessory_flag(title)` | `bool` |

## `_prep` fields (per product)

Standard: `_title`, `_norm`, `_brand`, `_level`, `_tokens`, `_flex`, `_hand`, `_price_uah`, `_url`.  
Domain extensions: `_product_type`, `_sport_context`, `_goalie`, `_curve`, `_skate_fit`, `_size_tokens`, `_accessory_flag`.
