# RFC-006: PostgreSQL Backend Enablement

- **Status:** Draft
- **Date:** 2026-03-12
- **Owners:** Project maintainers
- **Related ADRs:** ADR-0006 — Support PostgreSQL as an Alternative Database Backend and Use Pydantic for Boundary Validation

## 1. Summary

This RFC defines the technical plan for enabling PostgreSQL as a first-class alternative database backend while preserving the current shared SQLAlchemy ORM and repository architecture.

The target architecture is:

- SQLite remains the default backend for local/lightweight usage;
- PostgreSQL becomes a supported and tested backend for production-grade deployments;
- the same ORM, repository, and service layer behavior is preserved across supported SQL backends;
- schema management for non-test environments is performed through Alembic.

This RFC does not introduce a separate PostgreSQL-specific persistence implementation. It formalizes backend portability within the existing SQLAlchemy-based architecture.

## 2. Motivation

The current project structure is already close to backend-neutral operation because it uses SQLAlchemy ORM models, session factories, and repository abstractions. However, practical operation is still SQLite-first.

This creates the following limitations:

1. production deployment guidance remains weaker than desired;
2. backend portability is implied but not yet fully validated;
3. some schema and model choices may be acceptable under SQLite but insufficiently strict for PostgreSQL-backed long-term operation;
4. the absence of a PostgreSQL validation matrix leaves repository/service portability unproven.

The project needs a clear path from “SQLite-first, PostgreSQL-possible” to “SQLite-supported, PostgreSQL-supported”.

## 3. Goals

This RFC defines the work required to achieve the following goals:

1. run the application against PostgreSQL using the same SQLAlchemy ORM and repository layer used for SQLite;
2. make PostgreSQL a supported backend in development, CI, and production-oriented deployment;
3. ensure schema creation and upgrades for PostgreSQL are Alembic-driven;
4. identify and resolve schema/model choices that are unsafe or weak under cross-backend operation;
5. provide a repository/service test matrix covering SQLite and PostgreSQL;
6. preserve current project structure and avoid backend-specific service forks.

## 4. Non-Goals

This RFC does not:

1. replace SQLite as the default local/developer backend;
2. introduce a new persistence abstraction or separate PostgreSQL repositories;
3. redesign the domain model;
4. migrate the project away from Flask;
5. define all future PostgreSQL-specific optimizations;
6. require immediate use of PostgreSQL-specific SQL features such as dialect-specific upserts, custom enum types, or partitioning.

## 5. Current State

The current persistence architecture already includes the following enabling characteristics:

1. SQLAlchemy ORM models define the main relational schema;
2. repository logic is largely written against SQLAlchemy sessions rather than raw SQLite-specific SQL;
3. engine/session construction is already abstracted behind initialization helpers;
4. Alembic exists as the intended migration path.

However, the current state also includes important gaps and risks:

1. effective operation is still primarily SQLite-first;
2. runtime schema creation is still convenient enough that it may be used where Alembic should be authoritative;
3. some column types, especially floating-point price fields, are not ideal for long-term PostgreSQL-backed correctness;
4. backend portability is not yet enforced by CI;
5. some repository flows may need stronger integrity/error handling under concurrent writes.

## 6. Proposed Design

### 6.1 Backend support model

The application SHALL support both SQLite and PostgreSQL through a shared SQLAlchemy stack:

- one ORM model set;
- one repository layer;
- one service-layer behavior model.

Backend-specific differences SHALL be limited to:

1. SQLAlchemy engine configuration;
2. Alembic migration execution;
3. selected schema type corrections;
4. backend-specific testing setup;
5. explicitly documented optimizations, if introduced later.

### 6.2 Runtime configuration

Database backend selection SHALL be controlled by configuration, using the existing database URL mechanism.

The application SHALL:

1. continue to support SQLite as the default development backend;
2. accept PostgreSQL connection URLs through the same configuration pathway;
3. avoid branching application business logic based on backend choice.

Example backend selection model:

- SQLite for local default/developer workflows;
- PostgreSQL via explicit environment configuration for integration and deployment use.

### 6.3 Schema management model

For non-test environments, schema setup and evolution SHALL be Alembic-driven.

The project SHALL distinguish between:

1. **test-only schema bootstrap paths**, which may still use fast setup helpers where appropriate;
2. **runtime/deployment schema management**, which SHALL use Alembic migrations.

Runtime auto-creation of database schema SHALL NOT remain the canonical production pattern.

### 6.4 Cross-backend schema review

The schema SHALL be reviewed with explicit attention to cross-backend correctness.

The following areas require mandatory review.

#### 6.4.1 Exact numeric values

Any field representing prices, monetary values, or exact comparable business quantities SHOULD use exact numeric storage instead of binary floating-point representation.

Expected direction:

- move price-like fields from floating-point types to exact numeric/decimal-compatible types;
- keep application-level conversion and serialization behavior explicit.

#### 6.4.2 Status-like constrained fields

String fields that behave like controlled status/state enums SHOULD be reviewed for stronger invariants.

Initial direction:

- keep plain strings if necessary for compatibility;
- document allowed values centrally;
- optionally add stricter constraints later through a dedicated ADR/RFC.

#### 6.4.3 JSON and timestamp fields

JSON and timezone-aware timestamp usage SHALL be reviewed to ensure consistent behavior between SQLite and PostgreSQL.

This review SHALL explicitly verify:

- serialization/deserialization expectations;
- nullability behavior;
- timezone assumptions;
- migration behavior.

#### 6.4.4 Integrity and uniqueness under concurrency

Repository flows that currently implement “lookup then insert/update” patterns SHALL be reviewed for correctness under PostgreSQL concurrency.

The initial goal is not to introduce backend-specific SQL, but to ensure:

- integrity violations are handled predictably;
- retry/error behavior is defined where needed;
- repository semantics remain stable across backends.

### 6.5 Testing model

The project SHALL introduce backend-aware testing at the repository and service layers.

The minimum expected matrix is:

1. SQLite test run;
2. PostgreSQL test run.

The following categories MUST be covered:

- repository CRUD and mapping flows;
- service-layer operations that depend on relational state;
- migration execution against PostgreSQL;
- schema bootstrap and configuration validation.

### 6.6 Operational posture

The intended operational posture after implementation is:

- SQLite remains acceptable for local development and lightweight use;
- PostgreSQL becomes the recommended backend for production-oriented deployment;
- Alembic is the authoritative schema path outside test-only workflows.

## 7. Implementation Plan

Implementation SHALL be delivered in phases.

### Phase 1: Formalize backend-neutral runtime behavior

Objectives:

1. review engine/session/bootstrap code paths;
2. verify application startup works cleanly with PostgreSQL configuration;
3. identify runtime assumptions that only hold under SQLite.

Deliverables:

- documented backend configuration behavior;
- cleaned startup path for PostgreSQL operation;
- documented separation between dev/test bootstrap and migration-driven setup.

### Phase 2: Review and correct schema-sensitive fields

Objectives:

1. identify fields with weak cross-backend correctness;
2. correct price-like numeric fields;
3. review JSON, timestamps, and constrained-string fields.

Deliverables:

- migration plan for corrected types;
- documented schema decisions for cross-backend compatibility;
- updated ORM definitions where required.

### Phase 3: Make Alembic the canonical non-test schema path

Objectives:

1. remove ambiguity between runtime init and migration-driven schema management;
2. ensure PostgreSQL bootstrap and upgrade workflows are migration-first.

Deliverables:

- documented Alembic-first operational path;
- consistent migration execution guidance;
- verified migration flow for PostgreSQL from empty database to current schema.

### Phase 4: Add PostgreSQL test coverage

Objectives:

1. execute repository and service tests against PostgreSQL;
2. catch dialect-sensitive behavior before deployment use;
3. establish backend portability as a maintained property.

Deliverables:

- CI/backend matrix support;
- local integration test instructions;
- test coverage for core persistence flows.

### Phase 5: Stabilize deployment guidance

Objectives:

1. document PostgreSQL usage for real deployments;
2. define expected operational workflow;
3. identify any remaining backend-specific caveats.

Deliverables:

- deployment documentation;
- known limitations section;
- acceptance signoff for PostgreSQL support status.

## 8. Detailed Work Items

### 8.1 Configuration and startup

The following areas SHALL be reviewed and updated as needed:

1. database URL parsing and configuration defaults;
2. engine creation options;
3. session factory/scoped session behavior;
4. application startup bootstrapping behavior;
5. separation of dev convenience helpers from production schema handling.

### 8.2 ORM model review

The ORM model set SHALL be reviewed for:

1. exact numeric types vs floating-point types;
2. nullability correctness;
3. unique constraints and indexes;
4. JSON compatibility expectations;
5. timestamp semantics;
6. string length and text usage where backend behavior may differ.

### 8.3 Repository behavior review

Repositories SHALL be reviewed for:

1. assumptions about implicit ordering;
2. reliance on permissive SQLite coercion;
3. race-sensitive create/update flows;
4. predictable handling of missing rows and integrity failures;
5. transactional expectations.

### 8.4 Alembic review

Migration support SHALL be reviewed for:

1. clean schema creation on PostgreSQL;
2. upgrade path from initial migration to current state;
3. type changes required for portability;
4. compatibility of generated/handwritten migrations across both backends.

### 8.5 Testing and CI

The following SHALL be added or updated:

1. backend-specific test configuration;
2. PostgreSQL integration test environment;
3. CI job matrix for SQLite and PostgreSQL;
4. migration execution tests against PostgreSQL.

## 9. Risks

### 9.1 Type migration risk

Changing existing price-like fields from floating-point to exact numeric types may require data migration care, serialization review, and possible application-side adjustments.

### 9.2 Bootstrap ambiguity risk

If runtime schema initialization remains too permissive, developers may continue bypassing Alembic unintentionally, resulting in schema drift and inconsistent environments.

### 9.3 Concurrency behavior risk

Repository flows that behave correctly enough under SQLite may reveal uniqueness or transactional issues under PostgreSQL when concurrent writes are introduced.

### 9.4 Partial portability risk

Without a CI matrix, PostgreSQL support may appear correct in documentation while remaining insufficiently validated in practice.

## 10. Mitigations

The project SHOULD mitigate the above risks by:

1. introducing schema corrections before claiming PostgreSQL as fully supported;
2. making Alembic-first guidance explicit and normative;
3. adding backend matrix tests before production recommendation;
4. reviewing integrity-sensitive repository flows explicitly rather than relying on ad hoc discovery.

## 11. Acceptance Criteria

This RFC SHALL be considered implemented when all of the following are true:

1. the application runs against PostgreSQL using the same SQLAlchemy ORM and repository layer used for SQLite;
2. PostgreSQL schema creation and upgrades are performed through Alembic in non-test environments;
3. core repository and service tests pass against both SQLite and PostgreSQL;
4. identified cross-backend schema issues have documented resolutions;
5. no core business flow depends on undocumented SQLite-only behavior;
6. project documentation describes PostgreSQL as a supported backend with defined operational guidance.

## 12. Rollout Recommendation

The project SHOULD roll out PostgreSQL support in the following order:

1. establish backend-neutral startup and migration discipline;
2. correct schema-sensitive fields;
3. enable PostgreSQL test execution;
4. validate migration and CRUD/service flows;
5. document PostgreSQL as supported;
6. recommend PostgreSQL for production-oriented use only after the above steps are complete.

## 13. Open Questions

The following questions remain open and may require follow-up ADRs or implementation notes:

1. whether all price-like fields should become `Decimal` in both ORM and API serialization immediately;
2. whether status-like string fields should remain free strings or move to stricter constraints later;
3. whether any repository flows justify PostgreSQL-specific optimizations after portability is established;
4. whether runtime schema auto-creation should remain available at all outside tests.

## 14. Final Recommendation

PostgreSQL SHOULD be enabled as a first-class alternative backend through the existing SQLAlchemy architecture, not through a second persistence implementation.

The work should focus on:

- schema correctness,
- migration discipline,
- backend matrix testing,
- removal of SQLite-only assumptions.

This path provides a production-capable backend option while preserving architectural simplicity and minimizing unnecessary divergence.