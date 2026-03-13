/* service.scheduler.js — Scheduler UI bootstrap/orchestrator
 *
 * Logic is split across focused modules (loaded before this file):
 *   service.scheduler.state.js   — RUNNER_SPECS, schState
 *   service.scheduler.api.js     — fetch helpers, reference data loaders
 *   service.scheduler.render.js  — DOM rendering functions
 *   service.scheduler.forms.js   — modal form mapping / serialization
 *   service.scheduler.actions.js — action workflows, event wiring
 */
'use strict';

if (document.getElementById('tab-scheduler')) {
    // Expose schLoadJobs for service.js tab-switch integration
    window.schLoadJobs = schLoadJobs;
}
