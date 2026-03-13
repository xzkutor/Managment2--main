/* service.js — Service Console page bootstrap / tab orchestrator
 *
 * Tab-specific logic lives in dedicated modules loaded before this file:
 *   service.categories.js  — Categories tab (fetchAndCacheCategories,
 *                             loadCategoriesTable, renderCategoriesTable,
 *                             triggerCategorySync, syncCategoryProducts,
 *                             loadScrapeStatus)
 *   service.mappings.js    — Mappings tab (loadMappings, renderMappingsTable,
 *                             populateMappingCategorySelects, CRUD, events)
 *   service.history.js     — History tab (loadHistory, renderHistoryTable,
 *                             showRunDetails, events)
 *   service.scheduler.*    — Scheduler tab (already split)
 */
'use strict';

// Page guard: only run on service page
if (!document.getElementById('syncRefCategories')) { /* not this page */ }
else {

// ── Shared page state (referenced by all tab modules) ─────────────────

const serviceState = {
    stores: [],
    referenceStoreId: null,
    targetStoreId: null,
    mappingRefStoreId: null,
    mappingTargetStoreId: null,
    categories: {},
    mappings: [],
    history: { page: 0, pageSize: 10 },
    _listenersAttached: false,
};

// SERVICE_CONFIG is injected inline by the template as a global before this script loads.

// ── Tab switching ─────────────────────────────────────────────────────

const tabs = document.querySelectorAll('.tab-btn');
tabs.forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));

function switchTab(tab) {
    tabs.forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tab));
    document.querySelectorAll('main > section').forEach(s => {
        s.classList.toggle('hidden', s.id !== `tab-${tab}`);
    });
    if (tab === 'history')   loadHistory(true);
    if (tab === 'mappings')  loadMappings();
    if (tab === 'scheduler') window.schLoadJobs && window.schLoadJobs();
}

// ── Store sync ────────────────────────────────────────────────────────

async function syncStores() {
    if (!window.SERVICE_CONFIG || !SERVICE_CONFIG.enableAdminSync) return;
    const btn = document.getElementById('syncStoresBtn');
    if (btn) btn.disabled = true;
    setStatusPill('storeSyncStatus', 'Синхронізація магазинів…', 'warning');
    try {
        await fetchJson('/api/admin/stores/sync', { method: 'POST' });
        setStatusPill('storeSyncStatus', 'Магазини синхронізовано', 'success');
        await loadStores();
    } catch (err) {
        setStatusPill('storeSyncStatus', 'Помилка: ' + err.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ── Load stores (populates selects across all tabs) ───────────────────

async function loadStores() {
    try {
        const data = await fetchJson('/api/stores');
        serviceState.stores = data.stores || [];
        const options = ['<option value="">Оберіть</option>',
            ...serviceState.stores.map(s =>
                `<option value="${s.id}">${escHtml(s.name)}${s.is_reference ? ' (ref)' : ''}</option>`)
        ].join('');
        document.querySelectorAll(
            '#serviceRefStore, #serviceTargetStore, #mappingRefStore, #mappingTargetStore, #historyStoreFilter'
        ).forEach(sel => { sel.innerHTML = options; });
    } catch (err) {
        setStatusPill('refCategoriesStatus',    'Помилка магазинів: ' + err.message, 'error');
        setStatusPill('targetCategoriesStatus', 'Помилка магазинів: ' + err.message, 'error');
    }
}

// ── Page init: wires store selects and kicks off initial data loads ───

async function initStores() {
    if (!serviceState._listenersAttached) {
        serviceState._listenersAttached = true;

        document.getElementById('serviceRefStore').addEventListener('change', e => {
            serviceState.referenceStoreId = Number(e.target.value) || null;
            loadCategoriesTable('reference');
        });
        document.getElementById('serviceTargetStore').addEventListener('change', e => {
            serviceState.targetStoreId = Number(e.target.value) || null;
            loadCategoriesTable('target');
        });
        document.getElementById('mappingRefStore').addEventListener('change', async e => {
            serviceState.mappingRefStoreId = Number(e.target.value) || null;
            if (serviceState.mappingRefStoreId && !serviceState.categories[serviceState.mappingRefStoreId])
                await fetchAndCacheCategories(serviceState.mappingRefStoreId);
            loadMappings();
        });
        document.getElementById('mappingTargetStore').addEventListener('change', async e => {
            serviceState.mappingTargetStoreId = Number(e.target.value) || null;
            if (serviceState.mappingTargetStoreId && !serviceState.categories[serviceState.mappingTargetStoreId])
                await fetchAndCacheCategories(serviceState.mappingTargetStoreId);
            loadMappings();
        });
        document.getElementById('historyStoreFilter').addEventListener('change',   () => loadHistory(true));
        document.getElementById('historyTypeFilter').addEventListener('change',    () => loadHistory(true));
        document.getElementById('historyStatusFilter').addEventListener('change',  () => loadHistory(true));
        document.getElementById('historyTriggerFilter').addEventListener('change', () => loadHistory(true));

        if (window.SERVICE_CONFIG && SERVICE_CONFIG.enableAdminSync) {
            const ctrl = document.getElementById('storeSyncControls');
            if (ctrl) ctrl.classList.remove('hidden');
            document.getElementById('syncStoresBtn').addEventListener('click', syncStores);
        }

        document.getElementById('syncRefCategories').addEventListener('click', () =>
            triggerCategorySync(serviceState.referenceStoreId, 'refCategoriesStatus'));
        document.getElementById('syncTargetCategories').addEventListener('click', () =>
            triggerCategorySync(serviceState.targetStoreId, 'targetCategoriesStatus'));
    }
    await loadStores();
}

// ── Bootstrap ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initStores().then(() => {
        loadCategoriesTable('reference');
        loadCategoriesTable('target');
        loadScrapeStatus();
        loadHistory(true);
    });
});

} // end page guard

