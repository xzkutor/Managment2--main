/* service.mappings.js — Mappings tab logic */
'use strict';

// ── Data loading ──────────────────────────────────────────────────────

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

// ── Rendering ─────────────────────────────────────────────────────────

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
    document.getElementById('mappingTable').querySelectorAll('button[data-action]').forEach(btn =>
        btn.addEventListener('click', () => handleMappingAction(btn.dataset.action, Number(btn.dataset.id))));
}

function populateMappingCategorySelects(refStoreId, targetStoreId, refCatId = null, tgtCatId = null, disabled = false) {
    const refSel  = document.getElementById('mappingReferenceCategory');
    const tgtSel  = document.getElementById('mappingTargetCategory');
    const refCats = serviceState.categories[refStoreId]    || [];
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

// ── CRUD actions ──────────────────────────────────────────────────────

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
    if (action === 'edit')        editMapping(mappingId);
    else if (action === 'delete') deleteMapping(mappingId);
}

// ── Event wiring ──────────────────────────────────────────────────────

(function mappingsWireEvents() {
    const createBtn     = document.getElementById('createMappingBtn');
    const autoLinkBtn   = document.getElementById('autoLinkBtn');
    const mappingForm   = document.getElementById('mappingForm');
    const cancelBtn     = document.getElementById('mappingCancel');

    if (createBtn) createBtn.addEventListener('click', async () => {
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

    if (autoLinkBtn) autoLinkBtn.addEventListener('click', async () => {
        const refStoreId    = serviceState.mappingRefStoreId;
        const targetStoreId = serviceState.mappingTargetStoreId;
        if (!refStoreId || !targetStoreId) {
            setStatusPill('mappingStatus', 'Спочатку оберіть обидва магазини', 'warning'); return;
        }
        autoLinkBtn.disabled = true;
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
            autoLinkBtn.disabled = false;
        }
    });

    if (mappingForm) mappingForm.addEventListener('submit', e => {
        e.preventDefault();
        const dialog = document.getElementById('mappingModal');
        if (dialog.dataset.mode === 'edit') submitUpdateMapping(Number(dialog.dataset.mappingId));
        else submitCreateMapping();
    });

    if (cancelBtn) cancelBtn.addEventListener('click', () => {
        const dialog = document.getElementById('mappingModal');
        if (dialog.open) { dialog.close(); document.getElementById('mappingForm').reset(); }
    });
})();

