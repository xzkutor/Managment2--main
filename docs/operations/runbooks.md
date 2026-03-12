# Runbooks

## Purpose

This document captures operator-facing procedures for the existing service/admin workflows.
It focuses on what to do and what to verify, not on the deeper architectural rationale.

## 1. Initial data bootstrap

### Goal

Populate the database with stores, categories, products, mappings, and scrape history required for DB-first comparison.

### Procedure

1. Ensure the database schema is up to date.
2. Verify scraper adapters are configured and available.
3. Run category sync for the required stores.
4. Run product sync for the required store/category scope.
5. Review service/admin screens for mapping completeness and sync results.
6. Confirm the main comparison flow can read from DB without requiring live scraping.

### Verify

- stores exist
- categories exist for intended stores
- products are present and queryable
- scrape history reflects completed runs
- comparison works from persisted data

## 2. Store/category sync troubleshooting

### Symptoms

- categories missing in service panel
- product sync returns empty results
- comparison shows no products for a known populated store/category

### Checks

- verify target store exists and is active in DB
- verify category mappings are present where required
- inspect latest scrape run history
- inspect adapter selection/registry behavior
- check whether source extraction changed upstream

### Actions

- re-run sync for the affected scope
- compare adapter output with expected contract
- review logs/errors captured during scrape run
- update adapter if the upstream shop structure changed

## 3. Mapping review runbook

### Goal

Ensure confirmed mappings reflect operator-approved truth.

### Procedure

1. Open the service/admin mapping workflow.
2. Review unresolved or suspicious category/product relationships.
3. Distinguish between:
   - confirmed mapping to persist
   - candidate suggestion for review only
   - no valid mapping
4. Persist only confirmed mappings.
5. Re-run comparison or affected sync workflow if necessary.

### Verify

- confirmed mappings are visible as persisted truth
- comparison output improves predictably
- no candidate-only assumptions were accidentally persisted

## 4. Gap review runbook

### Goal

Triage assortment gaps shown in the gap workflow.

### Important model rule

`new` is an implicit state, not a necessarily persisted row.
Only non-default reviewed states may be stored explicitly.

### Procedure

1. Open the gap view for the desired scope.
2. Review visible gap items.
3. Set status according to operator intent:
   - leave as implicit `new`
   - mark `in_progress`
   - mark `done`
4. Revisit previously reviewed items when source data or mapping state changes.

### Verify

- reviewed statuses match current operator intent
- gap state is not mistaken for permanent product truth
- operators understand that visibility is context-dependent

## 5. Comparison output troubleshooting

### Symptoms

- expected reference products not shown
- false positives in matching
- too many unmatched results
- stale pricing/history behavior

### Checks

- confirm source data exists in DB
- confirm category mapping exists for the compared scope
- inspect confirmed product mappings
- inspect candidate-match heuristics and normalization behavior
- inspect freshness and latest scrape run state

### Actions

- fix missing or incorrect mappings
- re-run sync for stale datasets
- adjust matching heuristics only with accompanying tests and docs updates

## 6. Legacy/debug endpoint safety

### Rule

Internal or debug-oriented routes must not be treated as stable product contract.

### Operator guidance

- use them only for diagnosis, exploration, or migration support
- do not build primary UI/user flows around them
- if an endpoint becomes operationally required, move it into documented admin/service API

## 7. Before release or merge

Run this checklist:

- schema state is current
- core tests are green
- service/admin workflows still operate
- DB-first comparison still works without live scrape dependency
- docs were updated for any changed invariant, route, or workflow
