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

function priceStr(p) {
    if (!p) return '—';
    return p.price != null ? `${p.price} ${p.currency || ''}`.trim() : '—';
}

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
    const refId  = Number($refStoreFilter.value) || null;
    const tgtId  = Number($tgtStoreFilter.value) || null;
    const status = $statusFilter.value;
    const search = $searchFilter.value.trim();

    if (refId)   params.set('reference_store_id', refId);
    if (tgtId)   params.set('target_store_id', tgtId);
    if (status)  params.set('status', status);
    else         params.set('status', '');
    if (search)  params.set('search', search);

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

// ── Render table ──────────────────────────────────────────────────────
function renderTable(rows) {
    if (!rows.length) {
        $tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);">Немає даних</td></tr>';
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

