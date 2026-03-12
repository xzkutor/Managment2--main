# Outstanding Questions

## Purpose

This document tracks architectural and product questions that are not fully resolved yet, so they do not remain implicit or get solved accidentally in code.

## Open Questions

### 1. What is the supported surface of admin/service API?
The project already has a practical separation between DB-first product flow and operational/service routes. What remains to be decided is which admin routes are considered stable supportable contract versus maintainers-only internal tools.

Why it matters:
- affects OpenAPI scope;
- affects auth/exposure decisions;
- affects test and backward-compat expectations.

### 2. ~~Should route composition remain centralized in `app.py`?~~ ✅ Resolved
Routes have been extracted into `pricewatch/web/` Blueprint modules. `app.py` is now a composition and bootstrap layer only. See `docs/repository_map.md` for the current web-layer structure.

### 3. What is the long-term contract for response envelopes?
Some routes may already have de facto response shapes, but the project has not yet frozen a single response envelope convention across supported endpoints.

Why it matters:
- API contract clarity;
- frontend coupling reduction;
- OpenAPI generation readiness.

### 4. Is there any future for automated mapping confirmation?
The current documented model strongly favors persisted confirmed mappings and runtime-only candidates. It remains open whether some subset of high-confidence matches should be auto-confirmed.

Why it matters:
- data quality risk;
- operational workload;
- explainability and rollback requirements.

### 5. How should product identity drift be handled across store-side renames?
External stores may rename products, alter URLs, or rotate identifiers. The policy for preserving or repairing confirmed mappings under source drift should be made explicit.

Why it matters:
- durability of mapping truth;
- noisy remapping workload;
- false gaps and false misses.

### 6. Should comparison results ever be snapshotted?
Current direction is DB-first recomputation from persisted truth. It remains open whether historic comparison snapshots are useful for auditing, analytics, or UI history.

Why it matters:
- storage model;
- reproducibility of past states;
- complexity of freshness semantics.

### 7. What is the canonical identity key for gap status persistence?
The high-level model is clear, but the exact composition of the key used for explicit gap status rows should be documented with precision if not already obvious from schema/repository code.

Why it matters:
- prevents phantom reappearance or collision of statuses;
- improves debugging of `/gap` issues.

### 8. Should freshness become a first-class domain concept?
Today freshness can remain derived, but as the number of adapters/stores grows, explicit freshness semantics may become necessary.

Why it matters:
- UI transparency;
- stale-data handling;
- operational alerting and sync governance.

### 9. What is the retirement plan for legacy/debug endpoints?
The project has routes that are useful for development and diagnosis but should not define supported behavior. There should be a documented threshold for deprecation and removal.

Why it matters:
- reduces accidental dependency;
- simplifies API story;
- lowers maintenance burden.

### 10. Are there future authentication/authorization boundaries?
Current documents focus on behavior, not auth model. If the project grows beyond single-operator/internal usage, roles and protected route groups will need explicit design.

Why it matters:
- exposure control;
- admin vs read-only usage;
- safe publication of operational endpoints.

## Resolution Rules

When an open question is resolved:
1. record the decision in an ADR if it is architectural;
2. update the affected spec document(s);
3. update tests if observable behavior changes;
4. remove or rewrite the corresponding entry here.

## Non-Goals

This document is not a brainstorming backlog. It should contain only questions that materially affect design, contracts, invariants, or maintainability.
