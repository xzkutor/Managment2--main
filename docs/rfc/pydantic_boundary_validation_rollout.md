# RFC-007: Pydantic Boundary Validation Rollout

- **Status:** Draft
- **Date:** 2026-03-12
- **Owners:** Project maintainers
- **Related ADRs:** ADR-0006 — Support PostgreSQL as an Alternative Database Backend and Use Pydantic for Boundary Validation

## 1. Summary

This RFC defines how the project will adopt Pydantic for validation and normalization at system boundaries while preserving SQLAlchemy ORM as the persistence model and avoiding unnecessary duplication of business logic.

The target state is:

- raw inbound payloads are validated through explicit schemas;
- service-layer boundary inputs are typed and normalized;
- synchronization/import flows use structured DTOs instead of ad hoc dictionary parsing;
- validation failures are handled consistently;
- SQLAlchemy ORM entities remain the canonical persistence model.

This RFC does not introduce a separate domain model layer and does not replace the current ORM-based persistence architecture.

## 2. Motivation

The current codebase contains a growing amount of manual validation, normalization, coercion, and defaulting logic in HTTP handlers and service-layer ingestion flows. This has several drawbacks:

1. input contracts are implicit rather than explicit;
2. validation logic is distributed and repetitive;
3. field coercion behavior is difficult to reason about consistently;
4. malformed payload handling is not standardized;
5. synchronization and import flows contain ad hoc defensive parsing that is hard to test exhaustively.

The project needs a boundary-validation approach that is explicit, testable, and maintainable, while remaining compatible with the current SQLAlchemy-first architecture.

## 3. Goals

This RFC defines the work required to achieve the following goals:

1. validate key HTTP request payloads with explicit Pydantic schemas;
2. introduce typed service-boundary DTOs where raw dictionaries are currently passed across layers;
3. normalize synchronization/import payloads through dedicated Pydantic models;
4. standardize validation error handling;
5. reduce duplicated parsing and normalization logic;
6. preserve SQLAlchemy ORM entities and repository behavior unchanged where possible.

## 4. Non-Goals

This RFC does not:

1. replace SQLAlchemy ORM models with Pydantic models;
2. introduce a separate rich domain model layer;
3. require immediate migration of every route and service in one step;
4. require response schemas for every endpoint from day one;
5. move the project away from Flask;
6. duplicate the same validation rules in multiple layers without justification.

## 5. Current State

The current application behavior includes several validation patterns that motivate this rollout:

1. route handlers accept raw JSON dictionaries and inspect them directly;
2. service-layer methods perform manual field extraction, coercion, and defaulting;
3. synchronization/import flows contain custom logic for handling alternative field names, empty values, and price parsing;
4. serialization and deserialization contracts are not yet fully formalized.

This state is functional, but it is increasingly costly to maintain and test.

## 6. Proposed Design

### 6.1 Validation boundary model

Pydantic SHALL be introduced at system boundaries only.

The main boundaries are:

1. HTTP request ingress;
2. service command/query ingress;
3. adapter/import/synchronization ingress;
4. selected response/serialization boundaries where useful.

Within this model:

- Pydantic is responsible for validation, coercion, normalization, and input contract definition;
- services operate on typed DTOs or already-validated primitives;
- repositories continue to work with SQLAlchemy entities and plain internal values;
- ORM entities remain persistence-facing structures, not request models.

### 6.2 Layer responsibilities

#### HTTP layer

The HTTP layer SHALL:

1. parse request JSON;
2. validate it against an explicit Pydantic schema;
3. return standardized validation errors on failure;
4. pass validated DTOs or normalized primitives into services.

The HTTP layer SHALL NOT contain long-term ad hoc field validation logic once a route is migrated.

#### Service layer

The service layer MAY accept:

1. validated Pydantic DTO instances; or
2. plain typed values extracted from DTOs.

The service layer SHALL remain responsible for business rules and application invariants that are not merely input-shape validation.

Pydantic SHALL NOT be treated as a substitute for domain/business validation.

#### Repository layer

The repository layer SHALL remain independent from Pydantic.

Repositories SHALL continue to work with SQLAlchemy sessions, ORM entities, and explicit scalar inputs.

Repository contracts MAY receive already-normalized values derived from DTOs, but repositories SHALL NOT depend on Pydantic BaseModel internals.

### 6.3 DTO categories

The project SHALL introduce Pydantic models in the following categories.

#### 6.3.1 Request DTOs

These models validate HTTP payloads for route handlers.

Examples include:

- create/update mapping requests;
- comparison/filter requests;
- synchronization trigger requests;
- review/confirmation actions;
- category-related create/update payloads.

#### 6.3.2 Sync/import DTOs

These models normalize inbound product/category data before service logic persists or compares it.

These DTOs SHOULD handle:

- alternative field names;
- optional fields with defaults;
- empty-string normalization;
- price parsing/coercion;
- URL normalization rules where appropriate;
- required identifier checks.

#### 6.3.3 Service command DTOs

Where service APIs currently accept loosely structured dictionaries, typed command DTOs SHOULD be introduced.

This is especially useful for flows with many optional flags or partially overlapping inputs.

#### 6.3.4 Response DTOs

Response DTOs MAY be introduced where they materially reduce duplicated serialization logic or clarify public API contracts.

Response DTO rollout is optional and secondary to request/sync validation.

## 7. Validation Rules

### 7.1 Shape validation vs business validation

This RFC distinguishes two categories of validation.

#### Shape validation

Handled by Pydantic:

- field presence;
- type coercion;
- basic format checks;
- normalization of empty/null-equivalent values;
- constrained literal values where appropriate;
- default value assignment.

#### Business validation

Handled by services and repositories as appropriate:

- uniqueness expectations;
- relational existence checks;
- state transition rules;
- conflict semantics;
- domain invariants beyond payload shape.

Pydantic SHALL NOT become the only validation mechanism in the application.

### 7.2 Normalization rules

Boundary DTOs SHOULD normalize data consistently.

Normalization examples include:

1. trimming leading/trailing whitespace;
2. converting empty strings to `None` where semantically correct;
3. handling alternative inbound aliases for the same conceptual field;
4. parsing numeric values from safe textual input where required;
5. making optional booleans and flags explicit.

Normalization logic SHOULD be centralized inside DTO definitions or clearly associated helper functions, not scattered across route handlers.

### 7.3 Error handling rules

Validation failures SHOULD produce a standardized HTTP error shape.

At minimum, the error contract SHOULD include:

1. a stable top-level error type/code;
2. human-readable summary text;
3. field-level validation details where available.

The application SHOULD avoid route-specific custom validation error formats once routes are migrated.

## 8. Rollout Strategy

Pydantic adoption SHALL be incremental.

### Phase 1: Foundation

Objectives:

1. add Pydantic dependency and validation conventions;
2. define project-local DTO organization;
3. define standardized validation error mapping.

Deliverables:

- DTO module structure;
- validation helper utilities if needed;
- documented route migration pattern.

### Phase 2: High-value request schemas

Objectives:

1. migrate the most error-prone or manually validated endpoints first;
2. eliminate repeated `dict.get(...)` parsing in key routes;
3. stabilize error response handling.

Priority candidates:

- mapping creation/update flows;
- comparison/filter inputs;
- review/confirmation actions;
- synchronization entry points.

Deliverables:

- first set of request DTOs;
- route-level validation integration;
- validation tests for migrated endpoints.

### Phase 3: Sync/import normalization DTOs

Objectives:

1. move synchronization/import normalization into dedicated DTO models;
2. reduce custom defensive parsing in sync services;
3. make ingestion behavior explicit and testable.

Priority candidates:

- product import/sync payloads;
- category import payloads;
- optional metadata-bearing inbound records.

Deliverables:

- product sync DTOs;
- category sync DTOs;
- normalization and malformed-input tests.

### Phase 4: Service command DTOs

Objectives:

1. introduce typed service commands where service signatures remain too loose;
2. reduce dictionary-shaped internal APIs between route and service layers.

Deliverables:

- typed command inputs for selected services;
- simpler and clearer service invocation paths.

### Phase 5: Optional response DTOs

Objectives:

1. standardize response shapes where it removes duplicated serializer logic;
2. improve API contract clarity selectively.

Deliverables:

- response DTOs only where they add clear value;
- no blanket rewrite requirement.

## 9. Project Structure Recommendation

A recommended structure is:

- `schemas/requests/`
- `schemas/sync/`
- `schemas/services/`
- `schemas/responses/`

Alternative naming such as `dto/` MAY be used if it better matches repository conventions.

The chosen structure SHALL make boundary schemas easy to discover and separate from ORM entities.

## 10. Detailed Work Items

### 10.1 Add DTO infrastructure

The project SHALL:

1. choose the canonical DTO package/module layout;
2. define Pydantic base conventions if needed;
3. define shared normalization helpers only where reuse is real.

### 10.2 Add standardized validation integration

The project SHALL:

1. add route-level validation entry points;
2. standardize conversion of Pydantic validation failures into HTTP responses;
3. ensure error payloads are consistent across migrated routes.

### 10.3 Migrate selected request payloads

The project SHALL prioritize routes where:

1. payload shape is already non-trivial;
2. optional fields are numerous;
3. manual parsing is repetitive;
4. malformed input handling has high defect risk.

### 10.4 Migrate sync/import flows

The project SHALL review synchronization services for:

1. alias-heavy field extraction;
2. empty/null normalization logic;
3. numeric parsing;
4. URL fallback logic;
5. required field enforcement.

These rules SHOULD move into dedicated DTOs where possible.

### 10.5 Add tests

The project SHALL add tests for:

1. valid payload acceptance;
2. malformed payload rejection;
3. normalization behavior;
4. field alias behavior;
5. service behavior with validated DTO input;
6. validation error response structure.

## 11. Risks

### 11.1 Mixed-style transition risk

During rollout, the codebase will temporarily contain both manual validation and DTO-based validation. This is acceptable but must be controlled.

### 11.2 Over-modeling risk

If every internal structure becomes a Pydantic model prematurely, the project may accumulate unnecessary schema duplication and lose simplicity.

### 11.3 Boundary leakage risk

If DTO concerns leak deeply into repositories or persistence internals, coupling may increase instead of decrease.

### 11.4 Business-rule confusion risk

There is a risk of incorrectly moving business validation into DTOs. This must be avoided.

## 12. Mitigations

The project SHOULD mitigate the above risks by:

1. migrating incrementally rather than all at once;
2. keeping Pydantic at boundaries only;
3. documenting the distinction between shape validation and business validation;
4. avoiding response DTO rollout unless it clearly removes duplication;
5. preserving repository independence from DTO implementation details.

## 13. Acceptance Criteria

This RFC SHALL be considered implemented when all of the following are true:

1. key HTTP payloads are validated through explicit Pydantic schemas;
2. synchronization/import flows use structured DTO-based normalization for core entities;
3. validation failures are returned through a standardized error contract;
4. core service and repository logic no longer depend on raw unvalidated route payloads;
5. SQLAlchemy ORM remains the persistence model;
6. validation tests cover the main migrated routes and sync flows.

## 14. Open Questions

The following questions remain open and may require follow-up notes or ADRs:

1. whether response DTOs should be standardized broadly or only for selected endpoints;
2. whether a single `schemas/` package or a `dto/` package better matches repository style;
3. whether some constrained string fields should move to shared enums/literals at DTO level;
4. whether validation error payloads should adopt a project-wide formal schema immediately.

## 15. Final Recommendation

The project SHOULD adopt Pydantic incrementally as the standard mechanism for validation and normalization at HTTP, service-boundary, and synchronization/import boundaries.

The rollout SHOULD focus on high-value ingress points first, preserve the current SQLAlchemy persistence model, and avoid unnecessary duplication of validation and business rules.