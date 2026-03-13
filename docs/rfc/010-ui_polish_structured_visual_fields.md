# RFC-010: UI Polish and Structured Visual Fields for Scheduler Configuration

- **Status:** Draft
- **Date:** 2026-03-13
- **Owner:** Project maintainers
- **Related:** ADR-0009 UI Polish and Structured Visual Fields for Scheduler Configuration, ADR-0007 Scrape Runner and Scheduling Architecture, RFC-008 Scrape Scheduler MVP

## 1. Summary

This RFC defines the repository-aware implementation plan for improving the Service Console scheduler UI so that common job configuration is performed through structured visual fields instead of direct raw payload editing.

The scheduler backend is already present. The objective of this RFC is to make scheduler configuration visually manageable and operationally safer by improving create/edit/detail UX for jobs and schedules.

## 2. Goals

This RFC aims to:

- keep scheduler configuration inside the existing Service Console;
- make job targeting visually editable using explicit fields;
- map structured form state to and from `params_json` without breaking existing jobs;
- render key configuration fields in the job details panel;
- improve schedule editing UX with conditional fields;
- preserve repo fit and minimize frontend architectural churn.

## 3. Non-Goals

This RFC does not include:

- rewriting the whole frontend architecture;
- introducing a standalone scheduler page;
- advanced schema-driven form generation;
- live charts or metrics dashboards;
- cancellation UX;
- bulk edit/clone flows.

## 4. Repository Fit

The implementation must be constrained to the current UI surface and related assets.

### Primary UI touch points
- `templates/service.html`
- `static/js/service.js`
- `static/js/service.scheduler.js`
- `static/css/service.css`

### Existing UI assumptions
- Service Console already contains a `Scheduler` tab;
- scheduler list/detail/schedule/runs views already exist in MVP form;
- the frontend already calls scheduler-related admin endpoints.

This RFC improves the existing scheduler UI rather than replacing it.

## 5. Problem Statement

The current scheduler UI is functionally adequate, but several operator-facing gaps remain:

1. job targeting still relies too heavily on payload-style representation;
2. key fields such as store/category/runner relationship are not surfaced prominently enough;
3. the details panel still exposes internal structure more than intent;
4. the create/edit flow is less guided than it should be for common job types.

## 6. Design Principles

### 6.1 Structured fields first
The primary job form must use explicit fields for the most common scheduler configuration paths.

### 6.2 Raw payload only as fallback
`params_json` remains visible only in an advanced/debug section.

### 6.3 Runner-aware UI
Visible fields must depend on `runner_type`.

### 6.4 Backward compatibility
Existing jobs must remain editable even if they were created before structured UI mapping existed.

### 6.5 No silent data loss
When parsing legacy `params_json`, unsupported keys must either:
- be preserved, or
- remain visible in the advanced payload block.

## 7. Proposed UI Scope

## 7.1 Job create/edit modal
The modal will include structured fields for:

- `runner_type`
- `store_id` when relevant
- `category_id` when relevant
- `enabled`
- `allow_overlap`
- `timeout_sec`
- `max_retries`
- `retry_backoff_sec`

An advanced section may include:
- raw `params_json`
- compatibility notes

## 7.2 Schedule editor modal
The schedule form will expose:

- `schedule_type`
- `interval_sec` for interval schedules
- `cron_expr` for cron schedules
- `timezone` for cron schedules
- optional helper text / placeholders

The form must hide irrelevant inputs depending on selected schedule type.

## 7.3 Details panel
The selected job view must display labeled fields such as:

- Runner
- Store
- Category
- Enabled
- Overlap policy
- Timeout
- Retries
- Retry backoff
- Schedule type
- Cron / Interval
- Timezone
- Next run
- Last run

`params_json` may remain visible only in a collapsible advanced/debug section.

## 7.4 Jobs list polish
The jobs list should remain compact, but must become more informative.

Recommended visible fields or badges:
- runner type
- enabled/disabled
- schedule type
- next run
- optional overlap/retry badges if space permits

## 8. Runner-Aware Field Mapping

The frontend must define a local mapping between `runner_type` and visible target fields.

Examples:

### Store-targeted runner
Visible fields:
- store selector
- no category selector unless explicitly required

### Category-targeted runner
Visible fields:
- category selector
- optional store context if required by backend model

### Generic/full-sync runner
Visible fields:
- only fields relevant to that runner

This mapping belongs in `static/js/service.scheduler.js`.

## 9. Reference Data Loading

The UI must load enough reference data to populate visual selectors.

At minimum:
- stores
- categories

The UI should:
- lazily load data when entering the scheduler tab or opening the modal;
- cache reference data for the session where practical;
- gracefully handle empty or failed reference-data requests.

## 10. Form-State Mapping Rules

The frontend must implement two complementary paths:

### 10.1 API/job payload -> form state
When editing an existing job, the UI must parse:
- top-level job fields,
- known keys from `params_json`,
- existing schedule values.

### 10.2 Form state -> API payload
When saving a job, the UI must:
- serialize common structured fields into the expected API shape;
- preserve advanced payload keys that are not managed by the form when possible;
- avoid dropping unknown-but-existing payload fields silently.

## 11. Validation Requirements

### Client-side validation
- require store/category only where appropriate;
- numeric fields must be sane integers;
- hide irrelevant field errors when fields are not active;
- disable save while submit is in flight.

### Server-side validation handling
- display API validation errors clearly in the modal;
- show timezone/cron validation feedback inline where possible;
- avoid collapsing all scheduler save errors into generic alerts.

## 12. Styling and UX Hardening

The polish pass should include:
- consistent labels;
- compact but readable cards/rows;
- improved empty/loading/error states;
- selected-job visual emphasis;
- badge consistency for runner/status/schedule labels.

No major visual redesign is required.

## 13. Compatibility Requirements

The implementation must preserve:
- existing scheduler endpoints;
- existing Service Console tabs;
- editability of already-created jobs;
- ability to inspect raw payload for debugging.

The implementation must not require backend schema changes for this UI wave unless a separate RFC explicitly approves them.

## 14. Test and Review Scope

Manual or automated verification should cover:
- create job using only visual fields;
- edit existing legacy job with payload-only config;
- edit schedule visually;
- view readable key fields in details panel;
- save validation errors shown clearly;
- no regressions in existing Service Console tabs.

## 15. Acceptance Criteria

This RFC is complete when:

- common scheduler jobs can be created without raw JSON editing;
- store/category targeting is visually configurable;
- details panel shows key fields separately;
- schedule editing is conditional and readable;
- legacy jobs remain editable;
- advanced/raw payload view remains available but non-primary.

## 16. Deferred Work

Deferred beyond this RFC:
- schema-driven runner metadata for generic forms;
- cancellation UI;
- job cloning;
- bulk operations;
- live refresh dashboards;
- charts and metrics overlays.
