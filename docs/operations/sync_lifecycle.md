# Sync Lifecycle

## Purpose

This document describes how operational synchronization keeps DB-backed comparison usable.

## Principle

Synchronization is a write path into persistent storage.
Comparison is a read path from persistent storage.

These responsibilities must remain separate.

## Main lifecycle stages

### 1. Registry → stores
Administrative sync imports known adapters/stores into DB metadata.

### 2. Store → categories
Category sync reads categories from an adapter and persists them for a selected store.

### 3. Category → products
Product sync reads products for a selected category and persists them.

### 4. History capture
Each significant sync action should leave an operational record in scrape history.

## Operational expectations

- sync actions are launched from `/service` or admin API
- sync failures should be visible and inspectable
- stale data should be handled by prompting for refresh, not by changing comparison semantics

## Consistency expectations

After successful sync:
- stores should exist before categories depend on them
- categories should exist before products depend on them
- mappings should be reviewed after category structure changes
- comparisons should operate on the latest persisted state available

## Failure handling

When sync fails:
- the transaction should not leave partial silent corruption
- the error should be visible through API/UI feedback
- previous persisted data may remain, but freshness should be treated accordingly

## Recommended run order for operators

1. sync stores
2. sync categories for affected stores
3. review or create category mappings
4. sync products for mapped categories
5. run comparison or gap review

---

## Database configuration

- ORM: SQLAlchemy 2.x
- Default: SQLite (`sqlite:///pricewatch.db`)
- Easy migration to PostgreSQL via `DATABASE_URL` environment variable.
- Table creation at startup, except when `FLASK_ENV=production` or `DB_SKIP_CREATE_ALL=1`.

### Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Connection string, e.g. `postgresql+psycopg2://user:pass@host/db` or `sqlite+pysqlite:///:memory:` for tests |
| `DB_DEBUG_SQL` | `1` / `true` — enable SQL echo |
| `DB_SKIP_CREATE_ALL` | Skip automatic table creation at startup |
| `FLASK_ENV=production` | Also skips automatic table creation |

## Alembic migrations

Apply all pending migrations:
```bash
export DATABASE_URL=sqlite:///pricewatch.db
PYTHONPATH=. alembic upgrade head
```

Generate a new migration after changes to `pricewatch/db/models.py`:
```bash
PYTHONPATH=. alembic revision --autogenerate -m "short description"
PYTHONPATH=. alembic upgrade head
```

### Current migration versions

| File | Description |
|---|---|
| `095e10abb6f9_initial_schema.py` | Initial schema |
| `a1b2c3d4e5f6_add_gap_item_statuses.py` | Add `gap_item_statuses` table |

---

## Product DTO contract

When syncing products the service applies the following priority rules:

- `price` (numeric) — preferred field; used directly when present and valid.
- `price_raw` — fallback when `price` is absent; numeric value and currency are parsed from string.
- `currency` — explicit DTO value takes priority over currency parsed from `price_raw`.
- `source_url` — preferred source attribute; legacy fields (`source_site`, `url`) are used only as fallback.

Both dict objects and object DTOs (SimpleNamespace-compatible) are supported.
