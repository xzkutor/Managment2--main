/* matches.js — confirmed product mappings review page */
'use strict';

const state = {
    stores: [],
    refStoreId: null,
    tgtStoreId: null,
    status: 'confirmed',
    search: '',
};

// ── DOM refs ──────────────────────────────────────────────────────────
const $refStoreFilter  = document.getElementById('refStoreFilter');
const $tgtStoreFilter  = document.getElementById('tgtStoreFilter');
const $refCatFilter    = document.getElementById('refCatFilter');
const $tgtCatFilter    = document.getElementById('tgtCatFilter');
const $statusFilter    = document.getElementById('statusFilter');
const $searchFilter    = document.getElementById('searchFilter');
const $loadBtn         = document.getElementById('loadMatchesBtn');
const $summaryRow      = document.getElementById('summaryRow');
const $sumTotal        = document.getElementById('sumTotal');
const $statusEl        = document.getElementById('matchesStatus');
const $tableSection    = document.getElementById('matchesTableSection');
const $tableBody       = document.getElementById('matchesTableBody');

// ── Helpers ───────────────────────────────────────────────────────────
function setStatus(msg, type = 'info') {
    $statusEl.textContent = msg;
    $statusEl.className = `status-block ${type}`;
    $statusEl.classList.remove('hidden');
}

function clearStatus() {
    $statusEl.classList.add('hidden');
}

function productLink(p) {
    if (!p) return '—';
    return `<a class="link-btn" href="${escHtml(p.product_url || '#')}" target="_blank" rel="noopener">${escHtml(p.name || '—')}</a>`;
}

// priceStr — thin alias to shared formatProductPrice (defined in common.js)
function priceStr(p) { return formatProductPrice(p); }

function scorePill(confidence) {
    if (confidence == null) return '—';
    const pct = Math.round(confidence * 100);
    const cls = pct >= 85 ? '' : pct >= 65 ? 'medium' : 'low';
    return `<span class="score-pill ${cls}">${pct}%</span>`;
}

function statusBadge(status) {
    const label = status === 'confirmed' ? '✅ підтверджено' : status === 'rejected' ? '✖ відхилено' : escHtml(status || '—');
    const cls = status === 'confirmed' ? 'confirmed' : status === 'rejected' ? 'rejected' : '';
    return `<span class="status-badge ${cls}">${label}</span>`;
}

function fmtDate(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' }); }
    catch { return iso.slice(0, 10); }
}

// ── Load stores into filter selects ──────────────────────────────────
async function loadCategoriesForSelect(storeId, selectEl) {
    selectEl.innerHTML = '<option value="">— всі —</option>';
    if (!storeId) return;
    try {
        const data = await fetchJson(`/api/stores/${storeId}/categories`);
        const cats = data.categories || [];
        selectEl.innerHTML = '<option value="">— всі —</option>' +
            cats.map(c => `<option value="${c.id}">${escHtml(c.name)}</option>`).join('');
    } catch (_) { /* silently ignore */ }
}

async function loadStores() {
    try {
        const data = await fetchJson('/api/stores');
        const stores = data.stores || [];
        state.stores = stores;

        const refStores = stores.filter(s => s.is_reference);
        const tgtStores = stores.filter(s => !s.is_reference);

        $refStoreFilter.innerHTML = '<option value="">— всі —</option>' +
            refStores.map(s => `<option value="${s.id}">${escHtml(s.name)}</option>`).join('');
        $tgtStoreFilter.innerHTML = '<option value="">— всі —</option>' +
            tgtStores.map(s => `<option value="${s.id}">${escHtml(s.name)}</option>`).join('');

        $refStoreFilter.onchange = () => {
            const sid = Number($refStoreFilter.value) || null;
            loadCategoriesForSelect(sid, $refCatFilter);
        };
        $tgtStoreFilter.onchange = () => {
            const sid = Number($tgtStoreFilter.value) || null;
            loadCategoriesForSelect(sid, $tgtCatFilter);
        };
    } catch (err) {
        setStatus('Помилка завантаження магазинів: ' + err.message, 'error');
    }
}

// ── Load mappings ─────────────────────────────────────────────────────
async function loadMappings() {
    clearStatus();
    $tableSection.style.display = 'none';
    $summaryRow.classList.add('hidden');

    const params = new URLSearchParams();
    const refId    = Number($refStoreFilter.value) || null;
    const tgtId    = Number($tgtStoreFilter.value) || null;
    const refCatId = Number($refCatFilter.value)   || null;
    const tgtCatId = Number($tgtCatFilter.value)   || null;
    const status   = $statusFilter.value;
    const search   = $searchFilter.value.trim();

    if (refId)    params.set('reference_store_id', refId);
    if (tgtId)    params.set('target_store_id', tgtId);
    if (refCatId) params.set('reference_category_id', refCatId);
    if (tgtCatId) params.set('target_category_id', tgtCatId);
    if (status)   params.set('status', status);
    else          params.set('status', '');
    if (search)   params.set('search', search);

    setStatus('Завантаження…');
    try {
        const data = await fetchJson(`/api/product-mappings?${params}`);
        const rows = data.product_mappings || [];
        renderTable(rows);
        $sumTotal.textContent = rows.length;
        $summaryRow.classList.remove('hidden');
        clearStatus();
        $tableSection.style.display = rows.length ? '' : 'none';
        if (!rows.length) setStatus('Збігів не знайдено для обраних фільтрів.', 'info');
    } catch (err) {
        setStatus('Помилка завантаження: ' + err.message, 'error');
    }
}

// ── Delete mapping ────────────────────────────────────────────────────
async function deleteMapping(mappingId, btnEl) {
    if (!confirm(`Видалити маппінг #${mappingId}? Цю дію не можна скасувати.`)) return;
    btnEl.disabled = true;
    btnEl.textContent = '…';
    try {
        await fetchJson(`/api/product-mappings/${mappingId}`, { method: 'DELETE' });
        await loadMappings();
    } catch (err) {
        btnEl.disabled = false;
        btnEl.textContent = 'Видалити';
        setStatus('Помилка видалення: ' + err.message, 'error');
    }
}

// ── Render table ──────────────────────────────────────────────────────
function renderTable(rows) {
    if (!rows.length) {
        $tableBody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);">Немає даних</td></tr>';
        $tableSection.style.display = '';
        return;
    }
    $tableBody.innerHTML = rows.map(row => {
        const ref = row.reference_product || {};
        const tgt = row.target_product || {};
        const refCat = row.reference_category;
        const tgtCat = row.target_category;

        const refCatLabel = refCat
            ? `<div style="font-size:0.78rem;color:var(--muted);">${escHtml(refCat.name || '')}</div>`
            : '';
        const tgtCatLabel = tgtCat
            ? `<div style="font-size:0.78rem;color:var(--muted);">${escHtml(tgtCat.name || '')}</div>`
            : '';

        return `<tr>
            <td>${productLink(ref)}${refCatLabel}</td>
            <td>${priceStr(ref)}</td>
            <td>${productLink(tgt)}${tgtCatLabel}</td>
            <td>${priceStr(tgt)}</td>
            <td>${statusBadge(row.match_status)}</td>
            <td>${scorePill(row.confidence)}</td>
            <td>${fmtDate(row.updated_at)}</td>
            <td class="action-cell"><button class="btn btn-sm btn-reject"
                onclick="deleteMapping(${row.id}, this)">Видалити</button></td>
        </tr>`;
    }).join('');
    $tableSection.style.display = '';
}

// ── Event wiring ──────────────────────────────────────────────────────
$loadBtn.addEventListener('click', loadMappings);

$searchFilter.addEventListener('keydown', e => {
    if (e.key === 'Enter') loadMappings();
});

// ── Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', loadStores);

