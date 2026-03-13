# ADR-0009: UI Polish and Structured Visual Fields for Scheduler Configuration

- **Status:** Proposed
- **Date:** 2026-03-13
- **Decision Makers:** Project maintainers
- **Related:** ADR-0007 Scrape Runner and Scheduling Architecture, ADR-0008 Autostart Scheduler with the Application Runtime, RFC-008 Scrape Scheduler MVP, RFC-009 Scheduler Runtime Autostart Integration

## Context

The repository already contains a Service Console UI and a scheduler-capable backend for scrape jobs, schedules, manual enqueue, and run history. The current scheduler UI is functional, but it still exposes too much of the internal job payload model directly. In particular, job targeting and configuration are still too close to raw `params_json` instead of being represented through structured visual fields.

This creates the following problems:

1. common job configuration flows are harder to understand than necessary;
2. store/category/job targeting is less discoverable for operators;
3. the UI does not fully reflect the repo's current direction toward admin-safe, policy-driven scheduler control;
4. job details are readable, but not yet optimized for visual inspection and editing.

The repository already has the correct UI integration points:

- `templates/service.html`
- `static/js/service.js`
- `static/js/service.scheduler.js`
- `static/css/service.css`

The repository also already has backend support for scheduler-era operations, so this ADR is about improving the UI contract and operator experience, not changing the scheduler architecture.

## Decision

The project will evolve the Service Console scheduler UI from a raw-payload-oriented admin surface into a **structured visual configuration UI**.

The UI will:

- represent key job targeting fields as explicit form controls;
- keep `params_json` as an advanced/internal representation only;
- render key job configuration values in the details panel as separate readable fields;
- remain within the existing Service Console rather than introducing a new standalone scheduler page;
- reuse the current repo's service UI entry points and styling model.

## Decision Drivers

- Improve operator usability for common scheduler configuration tasks.
- Reduce reliance on raw JSON editing for standard flows.
- Preserve repo fit by extending existing Service Console assets instead of introducing a parallel UI architecture.
- Keep backward compatibility with existing jobs that may still rely on `params_json`.
- Ensure UI can visually configure store/category/runner/schedule relationships without exposing implementation details unnecessarily.

## Architectural Rules

### 1. Service Console remains the scheduler control-plane UI
The scheduler UI must continue to live inside the existing Service Console flow.

The implementation must extend:
- `templates/service.html`
- `static/js/service.js`
- `static/js/service.scheduler.js`
- `static/css/service.css`

It must not introduce a separate standalone page unless a later ADR explicitly approves such a split.

### 2. Structured fields are the primary editing path
The default scheduler job edit/create flow must expose explicit fields for common configuration.

At minimum, structured fields must cover:
- runner type
- store selection where applicable
- category selection where applicable
- enabled flag
- overlap policy
- timeout
- retry count
- retry backoff
- schedule type
- cron / interval / timezone where applicable

### 3. `params_json` remains advanced-only
`params_json` is retained as a storage and compatibility mechanism, but it must not be the primary UI used for standard job creation or editing.

The raw JSON view may remain available only as:
- an advanced section,
- a debug block,
- or a compatibility fallback.

### 4. UI remains runner-aware
The form must adapt visible target fields based on `runner_type`.

Examples:
- store-targeted runners show store selection;
- category-targeted runners show category selection;
- runners that require neither must hide those controls.

### 5. Job detail rendering must be readable without opening raw payloads
The selected job detail panel must render key configuration as labeled fields, badges, and schedule summaries rather than relying on raw JSON.

### 6. Backward compatibility is required
Existing jobs with only payload data in `params_json` must still open correctly in the editor and render meaningfully in the detail panel.

## Consequences

### Positive
- Better operator experience.
- Faster visual inspection of scheduler jobs.
- Lower risk of accidental malformed payload edits.
- Better alignment between backend policy and frontend affordances.
- Cleaner separation between internal representation and visual configuration.

### Negative
- Additional frontend state mapping logic is required.
- Form logic becomes more runner-aware and therefore more complex.
- Backward compatibility with existing payloads must be explicitly handled.

## Considered Options

### Option A — Keep raw `params_json` as the main editor
Rejected.

This would preserve minimal frontend complexity, but it would fail the goal of making scheduler configuration visually manageable for normal admin flows.

### Option B — Build a new standalone scheduler page
Rejected for now.

This would create unnecessary divergence from the existing Service Console structure and increase repo/UI complexity without enough benefit for the current scope.

### Option C — Extend Service Console with structured scheduler fields
Accepted.

This fits the repo, minimizes UI blast radius, and directly addresses operator usability.

## Implementation Guidance

The structured UI should be implemented in phases:

1. define runner-to-form-field mappings;
2. add structured fields to job create/edit modal;
3. load reference data for store/category selectors;
4. map structured fields to and from `params_json`;
5. improve schedule editing UX;
6. improve details panel rendering;
7. retain raw payload only as advanced/debug information.

## Acceptance Criteria

The ADR is considered satisfied when:

- a job for a specific store/category can be created without manual JSON editing;
- the selected job panel shows key fields as readable labeled values;
- existing jobs still render and can be edited correctly;
- schedule editing remains visual and type-aware;
- raw JSON is no longer required for standard scheduler flows.

## Non-Goals

This ADR does not authorize:

- a full frontend framework rewrite;
- schema-driven dynamic forms for all future runner types;
- cancellation UI;
- bulk job editing;
- charts or analytics dashboards;
- a separate scheduler application shell.

## Follow-up

A follow-up RFC should define:

- exact field mappings per runner type;
- detailed API assumptions for reference data loading;
- form-state serialization/deserialization rules;
- backward compatibility rules for legacy job payloads;
- validation and UX error behavior.
