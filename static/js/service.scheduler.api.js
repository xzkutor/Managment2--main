/* service.scheduler.api.js — Scheduler API helpers and reference data loaders */
'use strict';

// Patch fetchJson to expose HTTP status on errors (runs once)
(function patchFetchJson() {
    const _orig = window.fetchJson; if (!_orig) return;
    window.fetchJson = async function (url, opts) {
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            let msg;
            try { const j = await resp.json(); msg = j.message || j.error || resp.statusText; }
            catch { msg = resp.statusText; }
            const err = new Error(`${resp.status}: ${msg}`);
            err.status = resp.status; err.responseBody = msg; throw err;
        }
        return resp.json();
    };
})();

// ── Reference data loaders ────────────────────────────────────────────

async function schLoadStores() {
    if (schState.refData.stores !== null) return schState.refData.stores;
    if (schState.refData.loadingStores) return [];
    schState.refData.loadingStores = true;
    try {
        const d = await fetchJson('/api/stores');
        schState.refData.stores = d.stores || [];
    } catch { schState.refData.stores = []; }
    finally { schState.refData.loadingStores = false; }
    return schState.refData.stores;
}

async function schLoadCategories(storeId) {
    if (!storeId) return [];
    if (schState.refData.categories[storeId]) return schState.refData.categories[storeId];
    if (schState.refData.loadingCats[storeId]) return [];
    schState.refData.loadingCats[storeId] = true;
    try {
        const d = await fetchJson(`/api/stores/${storeId}/categories`);
        schState.refData.categories[storeId] = d.categories || [];
    } catch { schState.refData.categories[storeId] = []; }
    finally { schState.refData.loadingCats[storeId] = false; }
    return schState.refData.categories[storeId];
}

function _buildStoreOptions(sel) {
    const stores = schState.refData.stores || [];
    if (!stores.length) return '<option value="">Завантаження…</option>';
    return '<option value="">— оберіть магазин —</option>' +
        stores.map(s => `<option value="${s.id}" ${s.id == sel ? 'selected' : ''}>${escHtml(s.name)}${s.is_reference ? ' ★' : ''}</option>`).join('');
}

function _buildCatOptions(storeId, sel) {
    const cats = schState.refData.categories[storeId] || [];
    if (!cats.length) return '<option value="">Немає категорій</option>';
    return '<option value="">— оберіть категорію —</option>' +
        cats.map(c => `<option value="${c.id}" ${c.id == sel ? 'selected' : ''}>${escHtml(c.name)}</option>`).join('');
}

// ── API fetch wrappers ────────────────────────────────────────────────

async function schApiLoadJobs() {
    return fetchJson('/api/admin/scrape/jobs');
}

async function schApiLoadJobDetail(jobId) {
    return fetchJson(`/api/admin/scrape/jobs/${jobId}`);
}

async function schApiLoadJobRuns(jobId) {
    return fetchJson(`/api/admin/scrape/jobs/${jobId}/runs?limit=20`);
}

async function schApiRunNow(jobId) {
    return fetchJson(`/api/admin/scrape/jobs/${jobId}/run`, { method: 'POST' });
}

async function schApiToggleJob(jobId, enabled) {
    return fetchJson(`/api/admin/scrape/jobs/${jobId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
    });
}

async function schApiCreateJob(payload) {
    return fetchJson('/api/admin/scrape/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

async function schApiUpdateJob(jobId, patch) {
    return fetchJson(`/api/admin/scrape/jobs/${jobId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
    });
}

async function schApiSaveSchedule(jobId, payload) {
    return fetchJson(`/api/admin/scrape/jobs/${jobId}/schedule`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

