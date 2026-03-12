# Internal / Legacy / Debug API Specification

## Status

Draft. This document formalizes endpoints that exist in the repo but are **not** part of the stable DB-first product surface.

## Purpose

These endpoints are useful for:
- development-time debugging;
- adapter verification;
- parsing experiments;
- temporary or legacy operational flows.

They should be documented explicitly so they are not mistaken for long-term supported product APIs.

## Endpoint Family

README classifies the following as legacy/internal/debug:

- `GET /api/reference-products`
- `POST /api/check`
- `POST /api/parse-example`

## Non-Goals

These endpoints are not intended to:
- define the primary user journey;
- bypass the database-first model permanently;
- act as a stable external integration contract.

## Endpoint Notes

### `GET /api/reference-products`

Per README, this performs **live scraping** of the reference adapter by category.

#### Intended use
- adapter validation;
- quick diagnostic inspection;
- short-term troubleshooting during development.

#### Risks
- live scraping behavior can vary due to remote site changes;
- response time and reliability depend on external websites;
- result format can drift more easily than DB-backed endpoints.

#### Policy
- do not build new product UX on top of this endpoint;
- prefer persisted DB-backed flows for user-facing features;
- if retained, mark clearly as internal/diagnostic in code and docs.

---

### `POST /api/check`

Per README, this is a live scraping endpoint for arbitrary URLs and is explicitly described as debug.

#### Intended use
- trying an adapter against a raw URL;
- manual debugging;
- scraper development experiments.

#### Policy
- unsupported as a stable business API;
- may change or be removed without compatibility guarantees;
- should not be exposed to non-technical users.

---

### `POST /api/parse-example`

Per README, this parses an HTML fragment for debugging.

#### Intended use
- parser iteration;
- extraction rule testing;
- development-time diagnostics.

#### Policy
- treat as a test/support utility, not as a product contract;
- keep isolated from user-facing docs except in this internal spec.

## Stability Policy

All endpoints in this document are:
- implementation-facing;
- unstable by default;
- allowed to change without normal compatibility guarantees.

If any of them become necessary for supported workflows, they must be promoted into a stable document with:
- explicit request/response contract;
- validation rules;
- ownership;
- test coverage requirements.

## Cleanup Guidance

Long term, the repo should choose one of two directions per endpoint:
1. keep it, but label and test it as internal tooling;
2. remove it from runtime and replace it with test-only helper utilities.

## Documentation Rule

Root README may mention these endpoints briefly, but the canonical explanation for their status should live here so supported and unsupported APIs remain clearly separated.
