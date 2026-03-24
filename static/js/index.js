/* index.js — comparison page logic */
'use strict';

// Page guard: only run on the comparison page
if (!document.getElementById('compareBtn')) { /* not this page */ }
else {

const state = {
    stores: [],
    referenceStoreId: null,
    targetStoreId: null,
    referenceCategoryId: null,
    selectedTargetCategoryIds: new Set(),
    mappedTargets: [],
};

// ── DOM refs ─────────────────────────────────────────────────────────
const $mainStatus            = document.getElementById('mainStatus');
const $referenceStoreSelect  = document.getElementById('referenceStore');
const $targetStoreSelect     = document.getElementById('targetStore');
const $referenceCategoriesEl = document.getElementById('referenceCategories');
const $mappedTargetCategoriesEl = document.getElementById('mappedTargetCategories');

// ── Helpers ───────────────────────────────────────────────────────────
function setMainStatus(message, type = 'info') {
    if (!$mainStatus) return;
    $mainStatus.textContent = message;
    $mainStatus.style.background = type === 'error' ? '#ffe3e3' : '#eef1ff';
    $mainStatus.style.color      = type === 'error' ? '#b20000' : 'var(--muted)';
}

function clearMappedTargets() {
    $mappedTargetCategoriesEl.innerHTML = '<p class="muted">Оберіть категорію референсного магазину</p>';
}

function updateCompareBtn() {
    const btn = document.getElementById('compareBtn');
    if (!btn) return;
    btn.disabled = !(state.referenceCategoryId && state.selectedTargetCategoryIds.size > 0);
}

function scorePillHtml(pct, details) {
    if (pct == null) return '';
    const cls = pct >= 85 ? '' : pct >= 65 ? 'medium' : 'low';
    const tooltip = details ? JSON.stringify(details, null, 2) : '';
    return `<span class="tooltip-wrap"><span class="score-pill ${cls}">${pct}%</span>` +
        (tooltip ? `<span class="tooltip-box">${escHtml(tooltip)}</span>` : '') + `</span>`;
}

function catBadge(cat) {
    if (!cat) return '';
    return `<span class="badge badge-cat">${escHtml(cat.name || '')}` +
        (cat.store_name ? ` · ${escHtml(cat.store_name)}` : '') + `</span>`;
}

function productLink(p) {
    if (!p) return '—';
    return `<a class="link-btn" href="${escHtml(p.product_url || '#')}" target="_blank" rel="noopener">${escHtml(p.name || '—')}</a>`;
}

function priceStr(p) {
    if (!p) return '—';
    return p.price != null ? `${p.price} ${p.currency || ''}`.trim() : '—';
}

// ── Stores ────────────────────────────────────────────────────────────
async function loadStores() {
    setMainStatus('Завантажуємо магазини…');
    try {
        const data = await fetchJson('/api/stores');
        state.stores = data.stores || [];
        const refStores = state.stores.filter(s => s.is_reference);
        const tgtStores = state.stores.filter(s => !s.is_reference);

        $referenceStoreSelect.innerHTML = '<option value="">Оберіть магазин</option>' +
            refStores.map(s => `<option value="${s.id}">${escHtml(s.name)}</option>`).join('');
        $targetStoreSelect.innerHTML = '<option value="">Всі цільові магазини</option>' +
            tgtStores.map(s => `<option value="${s.id}">${escHtml(s.name)}</option>`).join('');

        $referenceStoreSelect.onchange = e => {
            state.referenceStoreId = Number(e.target.value) || null;
            state.referenceCategoryId = null;
            state.selectedTargetCategoryIds = new Set();
            state.mappedTargets = [];
            clearMappedTargets();
            updateCompareBtn();
            if (state.referenceStoreId)
                loadCategories(state.referenceStoreId, $referenceCategoriesEl);
        };

        $targetStoreSelect.onchange = e => {
            state.targetStoreId = Number(e.target.value) || null;
            state.selectedTargetCategoryIds = new Set();
            if (state.referenceCategoryId) loadMappedTargets(state.referenceCategoryId);
            updateCompareBtn();
        };

        if (refStores.length === 1) {
            $referenceStoreSelect.value = refStores[0].id;
            state.referenceStoreId = refStores[0].id;
            loadCategories(state.referenceStoreId, $referenceCategoriesEl);
        }
        setMainStatus('Оберіть референсну категорію для порівняння.');
    } catch (err) {
        setMainStatus('Помилка завантаження магазинів: ' + err.message, 'error');
    }
}

// ── Categories ────────────────────────────────────────────────────────
async function loadCategories(storeId, container) {
    container.innerHTML = '<p class="muted">Завантаження…</p>';
    try {
        const data = await fetchJson(`/api/stores/${storeId}/categories`);
        renderReferenceCategories(container, data.categories || []);
    } catch (err) {
        showError(container, err.message);
    }
}

function renderReferenceCategories(container, categories) {
    if (!categories.length) {
        container.innerHTML = '<p class="muted">Немає категорій. Синхронізуйте на сервісній сторінці.</p>';
        return;
    }
    container.innerHTML = '';
    categories.forEach(cat => {
        const div = document.createElement('div');
        div.className = 'category-item' + (state.referenceCategoryId === cat.id ? ' active' : '');
        div.innerHTML = `<strong>${escHtml(cat.name)}</strong><div class="muted">${escHtml(cat.url || 'Без URL')}</div>`;
        div.onclick = () => {
            state.referenceCategoryId = cat.id;
            state.selectedTargetCategoryIds = new Set();
            state.mappedTargets = [];
            renderReferenceCategories(container, categories);
            loadMappedTargets(cat.id);
            updateCompareBtn();
        };
        container.appendChild(div);
    });
}

// ── Mapped targets ────────────────────────────────────────────────────
async function loadMappedTargets(referenceCategoryId) {
    $mappedTargetCategoriesEl.innerHTML = '<p class="muted">Завантаження маппінгів…</p>';
    try {
        let url = `/api/categories/${referenceCategoryId}/mapped-target-categories`;
        if (state.targetStoreId) url += `?target_store_id=${state.targetStoreId}`;
        const data = await fetchJson(url);
        state.mappedTargets = data.mapped_target_categories || [];
        state.selectedTargetCategoryIds = new Set(state.mappedTargets.map(t => t.target_category_id));
        renderMappedTargets(state.mappedTargets);
        updateCompareBtn();
    } catch (err) {
        state.mappedTargets = [];
        state.selectedTargetCategoryIds = new Set();
        showError($mappedTargetCategoriesEl, err.message);
        updateCompareBtn();
    }
}

function renderMappedTargets(targets) {
    if (!targets.length) {
        $mappedTargetCategoriesEl.innerHTML =
            '<p class="muted" style="color:#92400e;background:#fef3c7;padding:10px 12px;border-radius:8px;">' +
            '⚠️ Для цієї категорії ще не створено меппінг. ' +
            'Перейдіть на <a href="/service" style="color:var(--accent);">сервісну сторінку</a> ' +
            'для створення маппінгу або запустіть авто-маппінг.</p>';
        return;
    }
    $mappedTargetCategoriesEl.innerHTML = '';
    targets.forEach(t => {
        const isChecked = state.selectedTargetCategoryIds.has(t.target_category_id);
        const div = document.createElement('div');
        div.className = 'mapped-target-item';
        const badge = t.match_type
            ? `<span style="font-size:0.75rem;background:#e0e7ff;color:#3730a3;padding:1px 7px;border-radius:999px;">${escHtml(t.match_type)}</span>`
            : '';
        div.innerHTML = `
            <input type="checkbox" id="tgt_${t.target_category_id}" ${isChecked ? 'checked' : ''}/>
            <label for="tgt_${t.target_category_id}" style="cursor:pointer;font-weight:normal;margin:0;flex:1;">
                <strong>${escHtml(t.target_category_name)}${badge}</strong>
                <div class="muted">${escHtml(t.target_store_name || '')}</div>
            </label>`;
        div.querySelector('input').addEventListener('change', e => {
            if (e.target.checked) state.selectedTargetCategoryIds.add(t.target_category_id);
            else state.selectedTargetCategoryIds.delete(t.target_category_id);
            updateCompareBtn();
        });
        $mappedTargetCategoriesEl.appendChild(div);
    });
}

// ── Comparison ────────────────────────────────────────────────────────
async function runComparison() {
    const statusEl  = document.getElementById('comparisonStatus');
    const resultsEl = document.getElementById('comparisonResults');
    statusEl.style.display = 'block';
    statusEl.textContent = 'Виконується порівняння…';
    statusEl.style.background = '#eef1ff';
    statusEl.style.color = 'var(--muted)';
    resultsEl.innerHTML = '';
    try {
        const body = {
            reference_category_id: state.referenceCategoryId,
            target_category_ids: Array.from(state.selectedTargetCategoryIds),
        };
        if (state.targetStoreId) body.target_store_id = state.targetStoreId;
        const data = await fetchJson('/api/comparison', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const s = data.summary || {};
        statusEl.textContent =
            `Підтверджено: ${s.confirmed_matches ?? 0}  •  ` +
            `Кандидатів: ${s.candidate_groups ?? 0}  •  ` +
            `Тільки в референсі: ${s.reference_only ?? 0}  •  ` +
            `Тільки в цільовому: ${s.target_only ?? 0}`;
        renderComparisonResults(resultsEl, data);
    } catch (err) {
        statusEl.textContent = 'Помилка: ' + err.message;
        statusEl.style.background = '#ffe3e3';
        statusEl.style.color = '#b20000';
    }
}

// ── Decision save (confirm / reject) ─────────────────────────────────
async function saveDecision(refId, tgtId, matchStatus) {
    return fetchJson('/api/comparison/match-decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            reference_product_id: refId,
            target_product_id: tgtId,
            match_status: matchStatus,
        }),
    });
}

// Compatibility shim — keep confirmMatch for any existing inline usage
async function confirmMatch(refId, tgtId, btnEl) {
    const compStatusEl = document.getElementById('comparisonStatus');
    btnEl.disabled = true;
    btnEl.textContent = '…';
    try {
        await saveDecision(refId, tgtId, 'confirmed');
        await refreshComparison();
    } catch (err) {
        btnEl.textContent = 'Помилка';
        btnEl.disabled = false;
        if (compStatusEl) {
            compStatusEl.textContent = 'Помилка збереження: ' + err.message;
            compStatusEl.style.background = '#ffe3e3';
            compStatusEl.style.color = '#b20000';
        }
    }
}

async function rejectMatch(refId, tgtId, btnEl) {
    const compStatusEl = document.getElementById('comparisonStatus');
    btnEl.disabled = true;
    btnEl.textContent = '…';
    try {
        await saveDecision(refId, tgtId, 'rejected');
        await refreshComparison();
    } catch (err) {
        btnEl.textContent = 'Помилка';
        btnEl.disabled = false;
        if (compStatusEl) {
            compStatusEl.textContent = 'Помилка відхилення: ' + err.message;
            compStatusEl.style.background = '#ffe3e3';
            compStatusEl.style.color = '#b20000';
        }
    }
}

// Re-run current comparison with the same state
async function refreshComparison() {
    if (!state.referenceCategoryId || state.selectedTargetCategoryIds.size === 0) return;
    await runComparison();
}

// ── Render: confirmed matches ─────────────────────────────────────────
function renderConfirmedMatches(container, matches) {
    const sec = document.createElement('div');
    sec.className = 'comp-section';
    sec.innerHTML = `<h3>✅ Підтверджені збіги <span class="badge badge-confirmed">${matches.length}</span></h3>`;
    if (!matches.length) {
        sec.innerHTML += '<p class="muted">Немає підтверджених збігів.</p>';
        container.appendChild(sec); return;
    }
    const rows = matches.map(m => {
        const ref = m.reference_product || {}, tgt = m.target_product || {};
        const isConfirmed = m.is_confirmed === true;
        const srcBadge = isConfirmed
            ? `<span class="badge badge-confirmed">💾 підтверджено</span>`
            : `<span class="badge badge-heuristic">🔍 авто</span>`;
        const confirmBtn = !isConfirmed
            ? `<button class="btn btn-sm" onclick="confirmMatch(${ref.id},${tgt.id},this)">✔ Підтвердити</button>`
            : '';
        const rejectBtn = `<button class="btn btn-sm btn-reject" onclick="rejectMatch(${ref.id},${tgt.id},this)">✖ Відхилити</button>`;
        return `<tr>
            <td>${productLink(ref)} ${srcBadge}</td>
            <td>${priceStr(ref)}</td>
            <td>${productLink(tgt)} ${catBadge(m.target_category)}</td>
            <td>${priceStr(tgt)}</td>
            <td>${scorePillHtml(m.score_percent, m.score_details)}</td>
            <td class="action-cell">${confirmBtn}${rejectBtn}</td>
        </tr>`;
    }).join('');
    sec.innerHTML += `<div class="table-wrapper"><table>
        <thead><tr><th>Референс</th><th>Ціна</th><th>Цільовий</th><th>Ціна</th><th>Score</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
    container.appendChild(sec);
}

// ── Render: candidate groups ──────────────────────────────────────────
function renderCandidateGroups(container, groups) {
    const sec = document.createElement('div');
    sec.className = 'comp-section';
    sec.innerHTML = `<h3>🔎 Групи кандидатів <span class="badge badge-ambig">${groups.length}</span></h3>`;
    if (!groups.length) {
        sec.innerHTML += '<p class="muted">Немає груп кандидатів.</p>';
        container.appendChild(sec); return;
    }
    groups.forEach(g => {
        const ref = g.reference_product || {};
        const card = document.createElement('div');
        card.className = 'candidate-card';

        // Heuristic candidates list
        const candidatesHtml = (g.candidates || []).map(c => {
            const tp = c.target_product || {}, canAccept = c.can_accept !== false;
            const disabledReason = c.disabled_reason ? ` title="${escHtml(c.disabled_reason)}"` : '';
            const acceptBtn = canAccept
                ? `<button class="btn btn-sm" onclick="confirmMatch(${ref.id},${tp.id},this)">✔ Прийняти</button>`
                : `<button class="btn btn-sm" disabled${disabledReason} style="opacity:0.4;">🚫 Вже використано</button>`;
            const rejectBtn = `<button class="btn btn-sm btn-reject" onclick="rejectMatch(${ref.id},${tp.id},this)">✖ Відхилити</button>`;
            return `<div class="candidate-item">${productLink(tp)} ${catBadge(c.target_category)}<span class="muted">${priceStr(tp)}</span>${scorePillHtml(c.score_percent, c.score_details)}${acceptBtn}${rejectBtn}</div>`;
        }).join('');

        // Manual picker
        const pickerId = `picker_${ref.id}`;
        const manualPickerHtml = `
        <div class="manual-picker" id="${pickerId}">
            <details class="picker-details">
                <summary class="picker-summary">🔍 Вибрати вручну…</summary>
                <div class="picker-body">
                    <input type="text" class="picker-search" placeholder="Пошук за назвою…"
                        oninput="loadPickerOptions(${ref.id}, this)"
                        data-ref-id="${ref.id}"/>
                    <select class="picker-select" size="5" id="pickerSelect_${ref.id}">
                        <option value="" disabled selected>— введіть запит —</option>
                    </select>
                    <button class="btn btn-sm" style="margin-top:6px;"
                        onclick="confirmPickerSelection(${ref.id}, this)">✔ Підтвердити вибір</button>
                </div>
            </details>
        </div>`;

        card.innerHTML = `<div class="ref-row">${productLink(ref)}<span class="muted"> — ${priceStr(ref)}</span></div>
        <div class="candidate-list">${candidatesHtml}</div>
        ${manualPickerHtml}`;
        sec.appendChild(card);
    });
    container.appendChild(sec);
}

// ── Manual picker logic ───────────────────────────────────────────────
let _pickerDebounce = null;

async function loadPickerOptions(refId, inputEl) {
    clearTimeout(_pickerDebounce);
    _pickerDebounce = setTimeout(async () => {
        const search = inputEl.value.trim();
        const selectEl = document.getElementById(`pickerSelect_${refId}`);
        if (!selectEl) return;
        if (search.length < 2) {
            selectEl.innerHTML = '<option value="" disabled>— введіть мінімум 2 символи —</option>';
            return;
        }
        selectEl.innerHTML = '<option disabled>Завантаження…</option>';
        try {
            const ids = Array.from(state.selectedTargetCategoryIds);
            const qs = ids.map(id => `target_category_ids=${id}`).join('&');
            const url = `/api/comparison/eligible-target-products?reference_product_id=${refId}&${qs}&search=${encodeURIComponent(search)}&limit=30`;
            const data = await fetchJson(url);
            const products = data.products || [];
            if (!products.length) {
                selectEl.innerHTML = '<option value="" disabled>— нічого не знайдено —</option>';
                return;
            }
            selectEl.innerHTML = products.map(p =>
                `<option value="${p.id}">${escHtml(p.name)} — ${p.price != null ? p.price + ' ' + (p.currency || '') : '?'}</option>`
            ).join('');
        } catch (err) {
            selectEl.innerHTML = `<option disabled>Помилка: ${escHtml(err.message)}</option>`;
        }
    }, 300);
}

async function confirmPickerSelection(refId, btnEl) {
    const selectEl = document.getElementById(`pickerSelect_${refId}`);
    if (!selectEl || !selectEl.value) return;
    const tgtId = parseInt(selectEl.value, 10);
    if (!tgtId) return;
    btnEl.disabled = true;
    btnEl.textContent = '…';
    try {
        await saveDecision(refId, tgtId, 'confirmed');
        await refreshComparison();
    } catch (err) {
        btnEl.disabled = false;
        btnEl.textContent = 'Помилка';
        const compStatusEl = document.getElementById('comparisonStatus');
        if (compStatusEl) {
            compStatusEl.textContent = 'Помилка підтвердження: ' + err.message;
            compStatusEl.style.background = '#ffe3e3';
            compStatusEl.style.color = '#b20000';
        }
    }
}
function renderOnlySideBySide(container, refOnly, tgtOnly) {
    const wrapper = document.createElement('div');
    wrapper.className = 'grid-side-by-side';

    const refDet = document.createElement('details');
    refDet.className = 'collapsible';
    refDet.innerHTML = `<summary>📋 Тільки в референсі <span class="badge badge-ref">${refOnly.length}</span></summary>`;
    const refBody = document.createElement('div');
    refBody.className = 'details-body';
    refBody.innerHTML = refOnly.length
        ? `<table><thead><tr><th>Назва</th><th>Ціна</th></tr></thead><tbody>${refOnly.map(item => {
            const p = item.reference_product || {};
            return `<tr><td>${productLink(p)}</td><td>${priceStr(p)}</td></tr>`;
          }).join('')}</tbody></table>`
        : '<p class="muted">Немає товарів тільки в референсі.</p>';
    refDet.appendChild(refBody);

    const tgtDet = document.createElement('details');
    tgtDet.className = 'collapsible';
    tgtDet.innerHTML = `<summary>📦 Тільки в цільовому <span class="badge badge-tgt">${tgtOnly.length}</span></summary>`;
    const tgtBody = document.createElement('div');
    tgtBody.className = 'details-body';
    tgtBody.innerHTML = tgtOnly.length
        ? `<table><thead><tr><th>Назва</th><th>Ціна</th></tr></thead><tbody>${tgtOnly.map(item => {
            const p = item.target_product || {};
            return `<tr><td>${productLink(p)} ${catBadge(item.target_category)}</td><td>${priceStr(p)}</td></tr>`;
          }).join('')}</tbody></table>`
        : '<p class="muted">Немає товарів тільки в цільовому.</p>';
    tgtDet.appendChild(tgtBody);

    wrapper.appendChild(refDet);
    wrapper.appendChild(tgtDet);
    container.appendChild(wrapper);
}

function renderComparisonResults(container, data) {
    container.innerHTML = '';
    renderConfirmedMatches(container, data.confirmed_matches || []);
    renderCandidateGroups(container, data.candidate_groups || []);
    renderOnlySideBySide(container, data.reference_only || [], data.target_only || []);
}

// Expose for inline onclick attributes
window.runComparison       = runComparison;
window.confirmMatch        = confirmMatch;
window.rejectMatch         = rejectMatch;
window.loadPickerOptions   = loadPickerOptions;
window.confirmPickerSelection = confirmPickerSelection;

document.addEventListener('DOMContentLoaded', loadStores);

} // end page guard

