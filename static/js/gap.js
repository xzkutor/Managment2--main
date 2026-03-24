/* gap.js — gap review page logic */
'use strict';

// Page guard: only run on the gap page
if (!document.getElementById('loadGapBtn')) { /* not this page */ }
else {

// ── State ─────────────────────────────────────────────────────────────
const state = {
    targetStoreId: null,
    refStores: [],
    targetStores: [],
    refCategories: [],
    mappedTargetCats: [],
};

// ── DOM refs ──────────────────────────────────────────────────────────
const $targetStoreSelect     = document.getElementById('targetStoreSelect');
const $refCategorySelect     = document.getElementById('refCategorySelect');
const $targetCatsContainer   = document.getElementById('targetCatsContainer');
const $targetCatsPlaceholder = document.getElementById('targetCatsPlaceholder');
const $searchInput           = document.getElementById('searchInput');
const $filterAvailable       = document.getElementById('filterAvailable');
const $statusNew             = document.getElementById('statusNew');
const $statusInProgress      = document.getElementById('statusInProgress');
const $statusDone            = document.getElementById('statusDone');
const $loadGapBtn            = document.getElementById('loadGapBtn');
const $noMappingsWarning     = document.getElementById('noMappingsWarning');
const $summaryRow            = document.getElementById('summaryRow');
const $statusArea            = document.getElementById('statusArea');
const $resultsArea           = document.getElementById('resultsArea');

// ── Status helpers ────────────────────────────────────────────────────
function showStatus(msg, type) {
    const cls = type === 'error' ? 'error' : type === 'warn' ? 'warn' : '';
    $statusArea.innerHTML = `<div class="status-msg ${cls}">${msg}</div>`;
}
function hideStatus() { $statusArea.innerHTML = ''; }

function escAttr(str) { return escHtml(str); }

// ── Init ──────────────────────────────────────────────────────────────
async function init() {
    showStatus('Завантаження магазинів…');
    try {
        const data = await fetchJson('/api/stores');
        const stores = data.stores || [];
        state.refStores    = stores.filter(s => s.is_reference);
        state.targetStores = stores.filter(s => !s.is_reference);

        $targetStoreSelect.innerHTML = '<option value="">— оберіть магазин —</option>';
        state.targetStores.forEach(s => {
            const o = document.createElement('option');
            o.value = s.id;
            o.textContent = s.name;
            $targetStoreSelect.appendChild(o);
        });
        hideStatus();
    } catch (e) {
        showStatus('Помилка завантаження магазинів: ' + e.message, 'error');
    }
}

// ── Target store → ref categories ─────────────────────────────────────
$targetStoreSelect.addEventListener('change', async () => {
    state.targetStoreId = $targetStoreSelect.value || null;
    $refCategorySelect.innerHTML = '<option value="">— завантаження… —</option>';
    $refCategorySelect.disabled = true;
    clearMappedCats();
    $loadGapBtn.disabled = true;
    $noMappingsWarning.classList.add('hidden');

    if (!state.targetStoreId) {
        $refCategorySelect.innerHTML = '<option value="">— спочатку оберіть магазин —</option>';
        return;
    }
    try {
        if (!state.refStores.length) {
            $refCategorySelect.innerHTML = '<option value="">Немає референсного магазину</option>';
            return;
        }
        const refStore = state.refStores[0];
        const data = await fetchJson(`/api/stores/${refStore.id}/categories`);
        state.refCategories = data.categories || [];

        $refCategorySelect.innerHTML = '<option value="">— оберіть категорію —</option>';
        state.refCategories.forEach(c => {
            const o = document.createElement('option');
            o.value = c.id;
            o.textContent = c.name + (c.product_count ? ` (${c.product_count})` : '');
            $refCategorySelect.appendChild(o);
        });
        $refCategorySelect.disabled = false;
    } catch (e) {
        $refCategorySelect.innerHTML = '<option value="">Помилка завантаження</option>';
    }
});

// ── Ref category → mapped target categories ───────────────────────────
$refCategorySelect.addEventListener('change', async () => {
    const refCatId = $refCategorySelect.value;
    clearMappedCats();
    $loadGapBtn.disabled = true;
    $noMappingsWarning.classList.add('hidden');

    if (!refCatId || !state.targetStoreId) return;

    $targetCatsPlaceholder.textContent = 'Завантаження маппінгів…';
    $targetCatsPlaceholder.classList.remove('hidden');

    try {
        const data = await fetchJson(
            `/api/categories/${refCatId}/mapped-target-categories?target_store_id=${state.targetStoreId}`
        );
        state.mappedTargetCats = data.mapped_target_categories || [];
        $targetCatsPlaceholder.classList.add('hidden');

        if (!state.mappedTargetCats.length) {
            $noMappingsWarning.classList.remove('hidden');
            $targetCatsPlaceholder.textContent = 'Немає маппінгів для цієї категорії';
            $targetCatsPlaceholder.classList.remove('hidden');
            $loadGapBtn.disabled = true;
            return;
        }

        state.mappedTargetCats.forEach(cat => {
            const label = document.createElement('label');
            label.className = 'multi-select-item';
            label.innerHTML = `<input type="checkbox" value="${cat.target_category_id}" checked>
                <span>${escHtml(cat.target_category_name)}</span>`;
            $targetCatsContainer.appendChild(label);
            label.querySelector('input').addEventListener('change', updateLoadBtn);
        });
        updateLoadBtn();
    } catch (e) {
        $targetCatsPlaceholder.textContent = 'Помилка завантаження маппінгів';
        $targetCatsPlaceholder.classList.remove('hidden');
    }
});

function clearMappedCats() {
    state.mappedTargetCats = [];
    $targetCatsContainer.querySelectorAll('.multi-select-item').forEach(el => el.remove());
    $targetCatsPlaceholder.textContent = 'Оберіть референсну категорію';
    $targetCatsPlaceholder.classList.remove('hidden');
}

function updateLoadBtn() {
    const anyChecked = $targetCatsContainer.querySelectorAll('input[type=checkbox]:checked').length > 0;
    $loadGapBtn.disabled = !anyChecked;
}

// ── Load gap ──────────────────────────────────────────────────────────
$loadGapBtn.addEventListener('click', loadGap);

async function loadGap() {
    const refCatId      = parseInt($refCategorySelect.value, 10);
    const targetStoreId = parseInt(state.targetStoreId, 10);
    const checkedIds    = Array.from(
        $targetCatsContainer.querySelectorAll('input[type=checkbox]:checked')
    ).map(el => parseInt(el.value, 10));

    if (!checkedIds.length) return;

    const statuses = [];
    if ($statusNew.checked)        statuses.push('new');
    if ($statusInProgress.checked) statuses.push('in_progress');
    if ($statusDone.checked)       statuses.push('done');

    const body = {
        target_store_id:       targetStoreId,
        reference_category_id: refCatId,
        target_category_ids:   checkedIds,
        search:                $searchInput.value.trim() || null,
        only_available:        $filterAvailable.checked || null,
        statuses:              statuses.length ? statuses : ['new', 'in_progress'],
    };

    showStatus('<span class="spinner"></span> Завантаження розриву…');
    $summaryRow.classList.add('hidden');
    $resultsArea.innerHTML = '';

    try {
        const data = await fetchJson('/api/gap', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        hideStatus();
        renderSummary(data.summary);
        renderGroups(data.groups, refCatId);
    } catch (e) {
        showStatus('Помилка запиту: ' + e.message, 'error');
    }
}

// ── Render summary ────────────────────────────────────────────────────
function renderSummary(summary) {
    document.getElementById('sumTotal').textContent      = summary.total       || 0;
    document.getElementById('sumNew').textContent        = summary.new         || 0;
    document.getElementById('sumInProgress').textContent = summary.in_progress || 0;
    document.getElementById('sumDone').textContent       = summary.done        || 0;
    $summaryRow.classList.remove('hidden');
}

// ── Render groups ─────────────────────────────────────────────────────
function renderGroups(groups, refCatId) {
    if (!groups || !groups.length) {
        $resultsArea.innerHTML = '<div class="status-msg">Розрив відсутній або всі товари відфільтровані.</div>';
        return;
    }
    $resultsArea.innerHTML = groups.map(group => {
        const catName = (group.target_category && group.target_category.name) || '—';
        const rows = (group.items || []).map(item => renderItemRow(item, refCatId)).join('');
        return `<div class="group-block panel">
            <div class="group-header">
                <h3>${escHtml(catName)}</h3>
                <span class="badge badge-cat">${group.count} товарів</span>
            </div>
            <table>
                <thead><tr><th>Назва</th><th>Ціна</th><th>Наявність</th><th>Статус</th><th>Дія</th><th>Посилання</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }).join('');

    $resultsArea.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', handleAction);
    });
}

function renderItemRow(item, refCatId) {
    const p      = item.target_product || {};
    const status = item.status || 'new';
    const price  = formatPrice(p.price, p.currency || '');
    const avail  = p.is_available
        ? '<span class="avail-yes">✓ є</span>'
        : '<span class="avail-no">✗ нема</span>';
    const badgeLabel = { new: 'Новий', in_progress: 'В роботі', done: 'Опрацьовано' }[status] || status;
    const link   = p.product_url
        ? `<a class="link-ext" href="${escAttr(p.product_url)}" target="_blank" rel="noopener">↗</a>`
        : '—';

    let actionBtn = '';
    if (status === 'new') {
        actionBtn = `<button class="btn btn-sm btn-action-take" data-action="in_progress"
            data-ref-cat="${refCatId}" data-prod-id="${p.id}">Взяти в роботу</button>`;
    } else if (status === 'in_progress') {
        actionBtn = `<button class="btn btn-sm btn-action-done" data-action="done"
            data-ref-cat="${refCatId}" data-prod-id="${p.id}">Позначити опрацьованим</button>`;
    } else {
        actionBtn = `<span class="badge badge-done">✓</span>`;
    }

    return `<tr data-prod-id="${p.id}">
        <td>${escHtml(p.name || '—')}</td>
        <td class="price-cell">${escHtml(price)}</td>
        <td>${avail}</td>
        <td><span class="badge badge-${status}">${badgeLabel}</span></td>
        <td>${actionBtn}</td>
        <td>${link}</td>
    </tr>`;
}

// ── Action handler ────────────────────────────────────────────────────
async function handleAction(e) {
    const btn       = e.currentTarget;
    const newStatus = btn.dataset.action;
    const refCatId  = parseInt(btn.dataset.refCat, 10);
    const prodId    = parseInt(btn.dataset.prodId, 10);
    const origText  = btn.textContent;

    btn.disabled    = true;
    btn.textContent = '…';

    try {
        await fetchJson('/api/gap/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reference_category_id: refCatId,
                target_product_id:     prodId,
                status:                newStatus,
            }),
        });
        // Reload to reflect updated statuses & summary
        await loadGap();
    } catch (e) {
        showStatus('Помилка зміни статусу: ' + e.message, 'error');
        btn.disabled    = false;
        btn.textContent = origText;
    }
}

// ── Boot ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);

} // end page guard

