# ADR-0006: Support PostgreSQL as an Alternative Database Backend and Use Pydantic for Boundary Validation

- **Status:** Proposed
- **Date:** 2026-03-12
- **Decision Makers:** Project maintainers
- **Related Documents:** RFC TBD — PostgreSQL backend enablement; RFC TBD — Pydantic validation rollout

## 1. Context

The project currently uses SQLAlchemy as the persistence abstraction and defaults to SQLite for local and lightweight execution. The current architecture already follows a shared ORM and repository approach and is close to backend-neutral operation, but practical support remains SQLite-first.

The project also contains a growing amount of manual validation and normalization logic at HTTP and service boundaries. This is especially visible in request payload handling and synchronization/import flows. Input contracts are often implicit, distributed across multiple layers, and not standardized.

The project now requires:

1. a production-suitable alternative database backend;
2. a stricter and more maintainable validation mechanism at system boundaries;
3. preservation of the current SQLAlchemy-based persistence model without introducing unnecessary parallel abstractions.

## 2. Decision

The project SHALL:

1. support **PostgreSQL** as an alternative runtime database backend;
2. retain a **single shared SQLAlchemy ORM and repository layer** for both SQLite and PostgreSQL;
3. adopt **Pydantic** for validation at system boundaries only;
4. continue using **SQLAlchemy ORM models as the persistence model**;
5. use **Alembic as the canonical schema migration mechanism** in non-test environments;
6. retain **SQLite as the default local/developer backend**.

The project SHALL NOT:

1. introduce separate SQLite-specific and PostgreSQL-specific repository implementations;
2. replace SQLAlchemy ORM entities with Pydantic models;
3. fork service-layer business logic by database backend;
4. rely on runtime schema auto-creation as the canonical production schema-management path.

## 3. Decision Details

### 3.1 Database backend strategy

PostgreSQL SHALL be introduced as an **alternative SQLAlchemy backend**, not as a separate persistence architecture.

The same ORM model set, repository contracts, and service behavior SHALL be preserved across supported SQL backends. Backend-specific differences SHALL be limited to configuration, migration handling, type correctness, and explicitly documented dialect-sensitive areas.

### 3.2 Validation strategy

Pydantic SHALL be used at system boundaries, including:

1. HTTP request payload validation;
2. service-layer input DTOs where raw dictionaries are currently passed across layers;
3. adapter/import/synchronization DTOs requiring normalization and coercion;
4. selected response DTOs where doing so removes duplicated serialization logic.

Pydantic SHALL NOT become the persistence model and SHALL NOT replace SQLAlchemy ORM entities.

## 4. Rationale

### 4.1 Why PostgreSQL

PostgreSQL provides a stronger long-term backend option for:

- concurrent access patterns;
- transactional reliability;
- production deployment;
- future indexing and query complexity;
- operational maturity beyond single-user or lightweight development usage.

SQLite remains appropriate for local development, lightweight operation, and simple bootstrap workflows, but it MUST NOT remain the only effectively supported backend.

### 4.2 Why a single persistence layer

The current use of SQLAlchemy already provides the correct architectural seam for supporting multiple SQL backends.

The requirement is backend portability, not multiple persistence implementations. A separate PostgreSQL-specific repository layer would duplicate behavior, increase test burden, and risk backend drift.

### 4.3 Why Pydantic

Pydantic provides:

- explicit and testable boundary contracts;
- centralized coercion and normalization;
- predictable validation failure behavior;
- reduced manual parsing and field-default logic;
- improved maintainability of synchronization and import flows.

### 4.4 Why not use Pydantic everywhere

The immediate problem is weak and scattered boundary validation, not the absence of a new primary model layer.

Introducing a full parallel Pydantic-driven application model would add complexity without proportionate benefit at this stage.

## 5. Architectural Rules Established by This ADR

### 5.1 Persistence rules

1. The project SHALL maintain a single SQLAlchemy ORM model set.
2. The project SHALL maintain a single repository and service behavior across supported SQL backends.
3. All production-grade schema evolution SHALL go through Alembic migrations.
4. New persistence code SHALL avoid undocumented SQLite-specific assumptions.
5. Core repository and service behavior SHALL be correct on both SQLite and PostgreSQL.
6. Backend-specific optimizations MAY be introduced later, but only if they do not change functional behavior and are explicitly documented.

### 5.2 Validation rules

1. New or refactored boundary-facing code SHOULD validate input using explicit Pydantic models.
2. Raw `dict`-driven validation SHALL NOT remain the target design for long-term API and sync flows.
3. Validation logic SHALL be concentrated at boundaries rather than duplicated across routes, services, and repositories.
4. Validation error handling SHOULD be standardized.
5. Repository internals SHALL NOT depend on Pydantic models.

## 6. Consequences

### 6.1 Positive consequences

1. PostgreSQL becomes a supported and production-suitable backend option.
2. SQLite remains available for lightweight local workflows.
3. Persistence architecture remains unified and maintainable.
4. Boundary contracts become explicit and testable.
5. Manual normalization and parsing logic is reduced.
6. Long-term maintainability and operational confidence improve.

### 6.2 Negative consequences

1. Some existing schema and model choices must be reviewed for cross-backend correctness.
2. Validation rollout will temporarily create mixed old/new validation styles.
3. Additional DTO definitions and tests will increase short-term implementation effort.
4. Some currently permissive flows may fail earlier and more explicitly once validation is formalized.

## 7. Required Follow-up Work

### 7.1 Backend enablement

The project MUST:

1. verify engine and session configuration for both SQLite and PostgreSQL;
2. ensure Alembic is the canonical non-test schema path;
3. add repository and service tests against PostgreSQL;
4. identify and remove SQLite-only assumptions in core flows.

### 7.2 Schema review

The project MUST review:

1. price-related fields currently represented as floating-point values;
2. status-like string fields that may require stricter constraints;
3. timestamp and JSON usage across supported backends;
4. uniqueness and integrity behavior under concurrent writes.

### 7.3 Validation rollout

The project MUST introduce Pydantic models for:

1. key HTTP request payloads;
2. synchronization and import DTOs;
3. selected service input contracts;
4. selected response DTOs where beneficial.

## 8. Alternatives Considered

### 8.1 Retain SQLite as the only backend

Rejected.

This would preserve the simplest immediate path but would not provide a stronger deployment option and would limit future operational maturity.

### 8.2 Create separate PostgreSQL-specific repositories

Rejected.

This would duplicate persistence logic, increase maintenance overhead, and create unnecessary divergence between supported backends.

### 8.3 Continue manual validation only

Rejected.

The current validation approach is already too distributed, repetitive, and weakly specified.

### 8.4 Replace SQLAlchemy entities with Pydantic-driven application models

Rejected for now.

This would be a larger architectural shift than is required to address the current persistence and validation needs.

## 9. Non-Goals

This ADR does not:

1. migrate the project away from Flask;
2. define detailed PostgreSQL-specific optimizations;
3. require immediate full response-schema standardization for all endpoints;
4. introduce a separate domain model layer;
5. allow backend-specific forks in service logic.

## 10. Acceptance Criteria

This ADR SHALL be considered implemented when all of the following are true:

1. the application can run against SQLite and PostgreSQL through the same SQLAlchemy and repository layer;
2. PostgreSQL schema setup and upgrades are performed through Alembic;
3. core boundary inputs are validated using Pydantic models;
4. core repository and service tests execute against both supported backends;
5. no core business flow depends on undocumented SQLite-specific behavior.

## 11. Status

Proposed.