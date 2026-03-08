/* service.js — service console page logic */
'use strict';

// Page guard: only run on service page
if (!document.getElementById('syncRefCategories')) { /* not this page */ }
else {

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
    if (tab === 'history') loadHistory(true);
    if (tab === 'mappings') loadMappings();
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

// ── Load stores ───────────────────────────────────────────────────────
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
        document.getElementById('historyStoreFilter').addEventListener('change',  () => loadHistory(true));
        document.getElementById('historyTypeFilter').addEventListener('change',   () => loadHistory(true));
        document.getElementById('historyStatusFilter').addEventListener('change', () => loadHistory(true));

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

// ── Categories ────────────────────────────────────────────────────────
async function fetchAndCacheCategories(storeId) {
    if (!storeId) return [];
    try {
        const data = await fetchJson(`/api/stores/${storeId}/categories`);
        serviceState.categories[storeId] = data.categories || [];
    } catch (_) {
        serviceState.categories[storeId] = [];
    }
    return serviceState.categories[storeId];
}

async function loadCategoriesTable(type) {
    const storeId  = type === 'reference' ? serviceState.referenceStoreId : serviceState.targetStoreId;
    const tableId  = type === 'reference' ? 'refCategoriesTable'    : 'targetCategoriesTable';
    const statusId = type === 'reference' ? 'refCategoriesStatus'   : 'targetCategoriesStatus';
    if (!storeId) {
        document.getElementById(tableId).innerHTML = '<p class="muted">Оберіть магазин</p>';
        setStatusPill(statusId, 'Очікування', 'info');
        return;
    }
    setStatusPill(statusId, 'Завантаження…', 'warning');
    try {
        const data = await fetchJson(`/api/stores/${storeId}/categories`);
        serviceState.categories[storeId] = data.categories || [];
        renderCategoriesTable(tableId, data.categories || [], type === 'reference');
        setStatusPill(statusId, `Категорій: ${data.categories.length}`, 'success');
    } catch (err) {
        setStatusPill(statusId, err.message, 'error');
        document.getElementById(tableId).innerHTML = '';
    }
}

function renderCategoriesTable(containerId, categories, isReference) {
    if (!categories.length) {
        document.getElementById(containerId).innerHTML = '<p class="muted">Немає категорій. Синхронізуйте дані.</p>';
        return;
    }
    const rows = categories.map(cat => `
        <tr>
            <td>${escHtml(cat.name)}</td>
            <td>${cat.updated_at ? new Date(cat.updated_at).toLocaleString() : '—'}</td>
            <td>${cat.product_count ?? 0}</td>
            <td><a href="${escHtml(cat.url || '#')}" target="_blank" rel="noopener">${cat.url ? 'Відкрити' : '—'}</a></td>
            <td><button class="ghost" data-cat="${cat.id}" data-store="${cat.store_id}" data-tab="${isReference ? 'reference' : 'target'}">Синхронізувати товари</button></td>
        </tr>`).join('');
    document.getElementById(containerId).innerHTML = `
        <table>
            <thead><tr><th>Назва</th><th>Оновлено</th><th>Продукти</th><th>URL</th><th>Дії</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
    document.getElementById(containerId).querySelectorAll('button[data-cat]').forEach(btn => {
        btn.addEventListener('click', () =>
            syncCategoryProducts(Number(btn.dataset.cat), btn.dataset.tab, Number(btn.dataset.store)));
    });
}

async function triggerCategorySync(storeId, statusId) {
    if (!storeId) { setStatusPill(statusId, 'Спочатку оберіть магазин', 'warning'); return; }
    setStatusPill(statusId, 'Запуск синхронізації…', 'warning');
    try {
        await fetchJson(`/api/stores/${storeId}/categories/sync`, { method: 'POST' });
        setStatusPill(statusId, 'Синхронізація завершена', 'success');
        const type = statusId === 'refCategoriesStatus' ? 'reference' : 'target';
        loadCategoriesTable(type);
        loadScrapeStatus();
    } catch (err) {
        setStatusPill(statusId, err.message, 'error');
    }
}

async function syncCategoryProducts(categoryId, tab = 'reference') {
    if (!categoryId) return;
    const statusId = tab === 'reference' ? 'refCategoriesStatus' : 'targetCategoriesStatus';
    setStatusPill(statusId, 'Синхронізація товарів…', 'warning');
    try {
        const res = await fetchJson(`/api/categories/${categoryId}/products/sync`, { method: 'POST' });
        const s = res && res.summary ? res.summary : null;
        const txt = s
            ? `processed ${s.products_processed ?? s.processed ?? 0} · created ${s.products_created ?? s.created ?? 0} · updated ${s.products_updated ?? s.updated ?? 0} · price changes ${s.price_changes_detected ?? s.price_changes ?? 0}`
            : 'Синхронізовано';
        setStatusPill(statusId, txt, 'success');
        loadScrapeStatus();
        loadCategoriesTable(tab);
        setTimeout(() => setStatusPill(statusId, 'Очікування', 'info'), 4000);
    } catch (err) {
        setStatusPill(statusId, 'Помилка: ' + err.message, 'error');
    }
}

// ── Scrape status ─────────────────────────────────────────────────────
async function loadScrapeStatus() {
    const container = document.getElementById('scrapeStatusList');
    if (!container) return;
    try {
        const data = await fetchJson('/api/scrape-status');
        const runs = data.runs || [];
        if (!runs.length) { container.innerHTML = ''; return; }
        container.innerHTML = runs.map(r => {
            const cls   = r.status === 'finished' ? 'finished' : r.status === 'failed' ? 'failed' : 'running';
            const store = r.store ? r.store.name : (r.store_id ? `store #${r.store_id}` : '—');
            const started = r.started_at ? new Date(r.started_at).toLocaleString() : '—';
            return `<div class="scrape-status-card ${cls}">
                <strong>${escHtml(store)}</strong>
                <div style="font-size:0.85rem;margin-top:4px;">${escHtml(r.run_type || '—')} · ${escHtml(r.status)}</div>
                <div style="font-size:0.8rem;color:#666;">${started}</div>
            </div>`;
        }).join('');
    } catch (_) { /* non-critical */ }
}

// ── Mappings ──────────────────────────────────────────────────────────
async function loadMappings() {
    const refStoreId    = serviceState.mappingRefStoreId;
    const targetStoreId = serviceState.mappingTargetStoreId;
    if (!refStoreId || !targetStoreId) {
        setStatusPill('mappingStatus', 'Виберіть обидва магазини для мапінгу', 'warning');
        document.getElementById('mappingTable').innerHTML = '';
        return;
    }
    setStatusPill('mappingStatus', 'Завантаження мапінгів…', 'warning');
    try {
        const data = await fetchJson(
            `/api/category-mappings?reference_store_id=${refStoreId}&target_store_id=${targetStoreId}`
        );
        serviceState.mappings = data.mappings || [];
        renderMappingsTable(data.mappings || []);
        setStatusPill('mappingStatus', `Знайдено мапінгів: ${serviceState.mappings.length}`, 'success');
    } catch (err) {
        setStatusPill('mappingStatus', 'Помилка завантаження: ' + err.message, 'error');
        document.getElementById('mappingTable').innerHTML = '';
    }
}

function renderMappingsTable(mappings) {
    if (!mappings.length) {
        document.getElementById('mappingTable').innerHTML = '<p class="muted">Немає мапінгів. Створіть новий.</p>';
        return;
    }
    const rows = mappings.map(m => `
        <tr>
            <td>${escHtml(m.reference_category_name || String(m.reference_category_id))}</td>
            <td>${escHtml(m.target_category_name    || String(m.target_category_id))}</td>
            <td>${escHtml(m.match_type || '—')}</td>
            <td>${m.confidence != null ? (m.confidence * 100).toFixed(0) + '%' : '—'}</td>
            <td>
                <button class="ghost" data-id="${m.id}" data-action="edit">Редагувати</button>
                <button class="ghost" data-id="${m.id}" data-action="delete">Видалити</button>
            </td>
        </tr>`).join('');
    document.getElementById('mappingTable').innerHTML = `
        <table>
            <thead><tr><th>Категорія (ref)</th><th>Категорія (target)</th><th>Тип</th><th>Confidence</th><th>Дії</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
    document.getElementById('mappingTable').querySelectorAll('button[data-action]').forEach(btn => {
        btn.addEventListener('click', () => handleMappingAction(btn.dataset.action, Number(btn.dataset.id)));
    });
}

function populateMappingCategorySelects(refStoreId, targetStoreId, refCatId = null, tgtCatId = null, disabled = false) {
    const refSel = document.getElementById('mappingReferenceCategory');
    const tgtSel = document.getElementById('mappingTargetCategory');
    const refCats = serviceState.categories[refStoreId] || [];
    const tgtCats = serviceState.categories[targetStoreId] || [];
    refSel.innerHTML = ['<option value="">Оберіть категорію</option>',
        ...refCats.map(c => `<option value="${c.id}" ${c.id == refCatId ? 'selected' : ''}>${escHtml(c.name)}</option>`)
    ].join('');
    tgtSel.innerHTML = ['<option value="">Оберіть категорію</option>',
        ...tgtCats.map(c => `<option value="${c.id}" ${c.id == tgtCatId ? 'selected' : ''}>${escHtml(c.name)}</option>`)
    ].join('');
    refSel.disabled = disabled;
    tgtSel.disabled = disabled;
}

document.getElementById('createMappingBtn').addEventListener('click', async () => {
    const refStoreId    = serviceState.mappingRefStoreId;
    const targetStoreId = serviceState.mappingTargetStoreId;
    if (!refStoreId || !targetStoreId) {
        setStatusPill('mappingStatus', 'Спочатку оберіть обидва магазини', 'warning'); return;
    }
    if (!serviceState.categories[refStoreId])    await fetchAndCacheCategories(refStoreId);
    if (!serviceState.categories[targetStoreId]) await fetchAndCacheCategories(targetStoreId);
    document.getElementById('mappingModalTitle').textContent = 'Новий мапінг';
    document.getElementById('mappingPairHint').textContent   = '';
    document.getElementById('mappingMatchType').value        = '';
    document.getElementById('mappingConfidence').value       = '';
    populateMappingCategorySelects(refStoreId, targetStoreId, null, null, false);
    const dialog = document.getElementById('mappingModal');
    dialog.dataset.mode = 'create';
    delete dialog.dataset.mappingId;
    dialog.showModal();
});

document.getElementById('autoLinkBtn').addEventListener('click', async () => {
    const refStoreId    = serviceState.mappingRefStoreId;
    const targetStoreId = serviceState.mappingTargetStoreId;
    if (!refStoreId || !targetStoreId) {
        setStatusPill('mappingStatus', 'Спочатку оберіть обидва магазини', 'warning'); return;
    }
    const btn = document.getElementById('autoLinkBtn');
    btn.disabled = true;
    setStatusPill('mappingStatus', 'Авто-маппінг…', 'warning');
    try {
        const data = await fetchJson('/api/category-mappings/auto-link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reference_store_id: refStoreId, target_store_id: targetStoreId }),
        });
        const s = data.summary || {};
        setStatusPill('mappingStatus',
            `Авто-маппінг завершено: створено ${s.created ?? 0}, вже існувало ${s.skipped_existing ?? 0}`,
            s.created > 0 ? 'success' : 'info');
        loadMappings();
    } catch (err) {
        setStatusPill('mappingStatus', 'Помилка авто-маппінгу: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
    }
});

document.getElementById('mappingForm').addEventListener('submit', e => {
    e.preventDefault();
    const dialog = document.getElementById('mappingModal');
    if (dialog.dataset.mode === 'edit') submitUpdateMapping(Number(dialog.dataset.mappingId));
    else submitCreateMapping();
});

document.getElementById('mappingCancel').addEventListener('click', () => {
    const dialog = document.getElementById('mappingModal');
    if (dialog.open) { dialog.close(); document.getElementById('mappingForm').reset(); }
});

async function submitCreateMapping() {
    const refCatId  = document.getElementById('mappingReferenceCategory').value;
    const tgtCatId  = document.getElementById('mappingTargetCategory').value;
    const matchType = document.getElementById('mappingMatchType').value.trim() || null;
    const conf      = document.getElementById('mappingConfidence').value;
    if (!refCatId || !tgtCatId) {
        setStatusPill('mappingStatus', 'Оберіть категорії для мапінгу', 'warning'); return;
    }
    setStatusPill('mappingStatus', 'Створення…', 'warning');
    try {
        await fetchJson('/api/category-mappings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reference_category_id: Number(refCatId),
                target_category_id:    Number(tgtCatId),
                match_type:  matchType,
                confidence:  conf ? parseFloat(conf) : null,
            }),
        });
        setStatusPill('mappingStatus', 'Мапінг створено', 'success');
        const dialog = document.getElementById('mappingModal');
        if (dialog.open) { dialog.close(); document.getElementById('mappingForm').reset(); }
        loadMappings();
    } catch (err) {
        setStatusPill('mappingStatus', 'Помилка: ' + err.message, 'error');
    }
}

function editMapping(mappingId) {
    const mapping = serviceState.mappings.find(m => m.id === mappingId);
    if (!mapping) return;
    const refStoreId    = serviceState.mappingRefStoreId;
    const targetStoreId = serviceState.mappingTargetStoreId;
    document.getElementById('mappingModalTitle').textContent = 'Редагувати мапінг';
    document.getElementById('mappingPairHint').textContent   = 'Пара категорій незмінна при редагуванні.';
    document.getElementById('mappingMatchType').value  = mapping.match_type || '';
    document.getElementById('mappingConfidence').value = mapping.confidence != null ? mapping.confidence : '';
    populateMappingCategorySelects(refStoreId, targetStoreId,
        mapping.reference_category_id, mapping.target_category_id, true);
    const dialog = document.getElementById('mappingModal');
    dialog.dataset.mode      = 'edit';
    dialog.dataset.mappingId = String(mappingId);
    dialog.showModal();
}

async function submitUpdateMapping(mappingId) {
    const matchType = document.getElementById('mappingMatchType').value.trim() || null;
    const conf      = document.getElementById('mappingConfidence').value;
    setStatusPill('mappingStatus', 'Оновлення…', 'warning');
    try {
        await fetchJson(`/api/category-mappings/${mappingId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ match_type: matchType, confidence: conf !== '' ? parseFloat(conf) : null }),
        });
        setStatusPill('mappingStatus', 'Мапінг оновлено', 'success');
        const dialog = document.getElementById('mappingModal');
        if (dialog.open) { dialog.close(); document.getElementById('mappingForm').reset(); }
        loadMappings();
    } catch (err) {
        setStatusPill('mappingStatus', 'Помилка: ' + err.message, 'error');
    }
}

async function deleteMapping(mappingId) {
    if (!confirm('Видалити цей мапінг?')) return;
    setStatusPill('mappingStatus', 'Видалення…', 'warning');
    try {
        await fetchJson(`/api/category-mappings/${mappingId}`, { method: 'DELETE' });
        setStatusPill('mappingStatus', 'Мапінг видалено', 'success');
        loadMappings();
    } catch (err) {
        setStatusPill('mappingStatus', 'Помилка: ' + err.message, 'error');
    }
}

function handleMappingAction(action, mappingId) {
    if (action === 'edit')   editMapping(mappingId);
    else if (action === 'delete') deleteMapping(mappingId);
}

// ── History ───────────────────────────────────────────────────────────
async function loadHistory(reset = false) {
    if (reset) serviceState.history.page = 0;
    const { page, pageSize } = serviceState.history;
    const storeId = document.getElementById('historyStoreFilter').value  || null;
    const runType = document.getElementById('historyTypeFilter').value   || null;
    const status  = document.getElementById('historyStatusFilter').value || null;
    const params  = new URLSearchParams();
    if (storeId)  params.set('store_id',  storeId);
    if (runType)  params.set('run_type',  runType);
    if (status)   params.set('status',    status);
    params.set('limit',  String(pageSize));
    params.set('offset', String(page * pageSize));
    setStatusPill('historyStatus', 'Завантаження…', 'warning');
    try {
        const data = await fetchJson(`/api/scrape-runs?${params.toString()}`);
        const runs = data.runs || [];
        renderHistoryTable(runs);
        setStatusPill('historyStatus', `Записів: ${runs.length}`, runs.length ? 'success' : 'info');
        document.getElementById('historyPageLabel').textContent = `Сторінка ${page + 1}`;
        document.getElementById('historyPrev').disabled = page === 0;
    } catch (err) {
        setStatusPill('historyStatus', 'Помилка: ' + err.message, 'error');
        document.getElementById('historyTable').innerHTML = '';
    }
}

function renderHistoryTable(runs) {
    if (!runs.length) {
        document.getElementById('historyTable').innerHTML = '<p class="muted">Немає записів. Синхронізуйте дані.</p>';
        return;
    }
    const rows = runs.map(r => {
        const store     = r.store ? r.store.name : (r.store_id ? `#${r.store_id}` : '—');
        const date      = r.started_at ? new Date(r.started_at).toLocaleString() : '—';
        const type      = r.run_type === 'categories' ? 'Категорії' :
                          r.run_type === 'category_products' ? 'Товари' : (r.run_type || '—');
        const statusCls = r.status === 'finished' ? 'success' : r.status === 'failed' ? 'error' : 'warning';
        return `<tr>
            <td>${date}</td>
            <td>${escHtml(store)}</td>
            <td>${escHtml(type)}</td>
            <td><span class="status-pill status-${statusCls}">${escHtml(r.status)}</span></td>
            <td><button class="ghost" data-id="${r.id}" data-action="details">Деталі</button></td>
        </tr>`;
    }).join('');
    document.getElementById('historyTable').innerHTML = `
        <table>
            <thead><tr><th>Дата</th><th>Магазин</th><th>Тип</th><th>Статус</th><th>Дії</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
    document.getElementById('historyTable').querySelectorAll('button[data-action]').forEach(btn => {
        btn.addEventListener('click', () => handleHistoryAction(btn.dataset.action, Number(btn.dataset.id)));
    });
}

document.getElementById('historyPrev').addEventListener('click', () => {
    if (serviceState.history.page > 0) { serviceState.history.page--; loadHistory(); }
});
document.getElementById('historyNext').addEventListener('click', () => {
    serviceState.history.page++;
    loadHistory();
});

function handleHistoryAction(action, runId) {
    if (action === 'details') showRunDetails(runId);
}

async function showRunDetails(runId) {
    const dialog = document.getElementById('runDetailsModal');
    document.getElementById('runDetails').textContent = 'Завантаження…';
    dialog.showModal();
    try {
        const data = await fetchJson(`/api/scrape-runs/${runId}`);
        document.getElementById('runDetails').textContent = JSON.stringify(data.run || data, null, 2);
    } catch (err) {
        document.getElementById('runDetails').textContent = 'Помилка: ' + err.message;
    }
}

document.getElementById('runDetailsClose').addEventListener('click', () => {
    const d = document.getElementById('runDetailsModal');
    if (d.open) d.close();
});

// ── Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initStores().then(() => {
        loadCategoriesTable('reference');
        loadCategoriesTable('target');
        loadScrapeStatus();
        loadHistory(true);
    });
});

} // end page guard

