# Architecture Overview

## Summary

The application is a Flask-based product comparison system with a database-first user flow.

At a high level, the system is split into four layers:

1. presentation layer
   - `/` user-facing comparison UI
   - `/service` operational/admin UI
   - `/gap` content review UI for assortment gaps

2. application/services layer
   - store/category/product sync services
   - comparison orchestration
   - scrape history services
   - gap review services
   - mapping services

3. integration layer
   - store-specific scraping adapters
   - adapter registry and resolution by domain/source

4. persistence layer
   - SQLAlchemy models
   - Alembic migrations
   - repository functions over database tables

## Primary architectural principle

The primary product flow is database-first.

That means:
- user-facing comparison reads from persisted `stores`, `categories`, `products`
- comparison does not depend on live scraping
- live scraping exists to refresh persisted data, not to power the main UI directly

## Main runtime flows

### 1. Data acquisition flow

Registry / adapters
→ store sync
→ category sync
→ product sync
→ data persisted in DB
→ scrape run recorded in history

### 2. User comparison flow

User opens `/`
→ selects reference store / target store
→ selects reference category
→ system loads mapped target categories
→ user triggers comparison
→ comparison is built from DB records and mappings
→ user may confirm a match into persistent `ProductMapping`

### 3. Gap review flow

User opens `/gap`
→ selects target store and reference category
→ system loads mapped target categories
→ system calculates target-only products not covered by confirmed mappings or candidate groups
→ reviewer marks items as `in_progress` or `done`

## Boundary guidance

### What belongs in the main UI

- browsing DB-backed stores/categories/products
- comparing mapped categories
- showing confirmed matches, candidates, reference-only, target-only

### What belongs in the service UI

- sync operations
- category mapping CRUD
- scrape history inspection
- operational refresh actions

### What belongs in legacy/debug space

- direct parsing of arbitrary URLs
- HTML fragment debug parsing
- live scraping endpoints used for diagnostics

## Current code-level observation

The project already has meaningful internal separation in packages such as:
- `pricewatch/core`
- `pricewatch/db`
- `pricewatch/services`
- `pricewatch/shops`

However, `app.py` now acts purely as a composition and bootstrap layer — routes live in `pricewatch/web/` Blueprint modules. That makes architectural docs especially important for understanding the full request lifecycle.
