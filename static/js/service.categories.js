/* service.categories.js — Categories tab and scrape status logic */
'use strict';

// ── Shared category cache helper (also used by mappings tab) ──────────

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

// ── Data loading ──────────────────────────────────────────────────────

async function loadCategoriesTable(type) {
    const storeId  = type === 'reference' ? serviceState.referenceStoreId : serviceState.targetStoreId;
    const tableId  = type === 'reference' ? 'refCategoriesTable'  : 'targetCategoriesTable';
    const statusId = type === 'reference' ? 'refCategoriesStatus' : 'targetCategoriesStatus';
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

// ── Rendering ─────────────────────────────────────────────────────────

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
    document.getElementById(containerId).querySelectorAll('button[data-cat]').forEach(btn =>
        btn.addEventListener('click', () =>
            syncCategoryProducts(Number(btn.dataset.cat), btn.dataset.tab, Number(btn.dataset.store))));
}

// ── Actions ───────────────────────────────────────────────────────────

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
        const s   = res && res.summary ? res.summary : null;
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

// ── Scrape status widget ──────────────────────────────────────────────

async function loadScrapeStatus() {
    const container = document.getElementById('scrapeStatusList');
    if (!container) return;
    try {
        const data = await fetchJson('/api/scrape-status');
        const runs = data.runs || [];
        if (!runs.length) { container.innerHTML = ''; return; }
        container.innerHTML = runs.map(r => {
            const cls     = r.status === 'finished' ? 'finished' : r.status === 'failed' ? 'failed' : 'running';
            const store   = r.store ? r.store.name : (r.store_id ? `store #${r.store_id}` : '—');
            const started = r.started_at ? new Date(r.started_at).toLocaleString() : '—';
            return `<div class="scrape-status-card ${cls}">
                <strong>${escHtml(store)}</strong>
                <div style="font-size:0.85rem;margin-top:4px;">${escHtml(r.run_type || '—')} · ${escHtml(r.status)}</div>
                <div style="font-size:0.8rem;color:#666;">${started}</div>
            </div>`;
        }).join('');
    } catch (_) { /* non-critical */ }
}

