/* service.scheduler.forms.js — Scheduler modal form mapping and structured field logic */
'use strict';

// ── Runner-aware field visibility ─────────────────────────────────────

async function schUpdateRunnerFields(runnerType, selectedStoreId, selectedCatId) {
    const spec     = getRunnerUiSpec(runnerType);
    const storeGrp = document.getElementById('schJobStoreGroup');
    const catGrp   = document.getElementById('schJobCategoryGroup');
    if (storeGrp) storeGrp.classList.toggle('hidden', !spec.requiresStore);
    if (catGrp)   catGrp.classList.toggle('hidden',   !spec.requiresCategory);

    const storeHelp = document.getElementById('schJobStoreHelp');
    const catHelp   = document.getElementById('schJobCategoryHelp');
    if (storeHelp) storeHelp.textContent = spec.storeHelp || '';
    if (catHelp)   catHelp.textContent   = spec.categoryHelp || '';

    if (spec.requiresStore) {
        await schLoadStores();
        const sel = document.getElementById('schJobStoreId');
        if (sel) { sel.innerHTML = _buildStoreOptions(selectedStoreId); sel.required = true; }
    } else {
        const sel = document.getElementById('schJobStoreId');
        if (sel) sel.required = false;
    }
    if (spec.requiresCategory) {
        const storeId = selectedStoreId
            || parseInt(document.getElementById('schJobStoreId')?.value) || null;
        if (storeId) {
            await schLoadCategories(storeId);
            const catSel = document.getElementById('schJobCategoryId');
            if (catSel) { catSel.innerHTML = _buildCatOptions(storeId, selectedCatId); catSel.required = true; }
        }
    } else {
        const catSel = document.getElementById('schJobCategoryId');
        if (catSel) catSel.required = false;
    }
}

// ── Job form — deserialize params_json → form fields ─────────────────

function _hydrateJobForm(job) {
    const p = job.params_json || {};
    const knownKeys = new Set(['store_id', 'category_id']);
    const extra = Object.fromEntries(Object.entries(p).filter(([k]) => !knownKeys.has(k)));
    document.getElementById('schJobSourceKey').value      = job.source_key || '';
    document.getElementById('schJobSourceKey').disabled   = true;
    document.getElementById('schJobRunnerType').value     = job.runner_type || 'store_category_sync';
    document.getElementById('schJobEnabled').checked      = !!job.enabled;
    document.getElementById('schJobAllowOverlap').checked = !!job.allow_overlap;
    document.getElementById('schJobMaxRetries').value     = job.max_retries ?? 0;
    document.getElementById('schJobRetryBackoff').value   = job.retry_backoff_sec ?? 60;
    document.getElementById('schJobTimeoutSec').value     = job.timeout_sec || '';
    document.getElementById('schJobParamsJson').value     = Object.keys(extra).length ? JSON.stringify(extra, null, 2) : '';
    return { storeId: p.store_id || null, catId: p.category_id || null };
}

// ── Job form — serialize form fields → API payload ────────────────────

function _serializeJobForm() {
    const runnerType = document.getElementById('schJobRunnerType').value;
    const spec       = getRunnerUiSpec(runnerType);
    const sourceKey  = document.getElementById('schJobSourceKey').value.trim();
    if (!sourceKey) return { error: "Source key є обов'язковим" };

    const storeId = parseInt(document.getElementById('schJobStoreId')?.value) || null;
    const catId   = parseInt(document.getElementById('schJobCategoryId')?.value) || null;
    if (spec.requiresStore    && !storeId) return { error: 'Оберіть магазин' };
    if (spec.requiresCategory && !catId)   return { error: 'Оберіть категорію' };

    const maxRetries = parseInt(document.getElementById('schJobMaxRetries').value);
    const backoff    = parseInt(document.getElementById('schJobRetryBackoff').value);
    const timeout    = parseInt(document.getElementById('schJobTimeoutSec').value) || null;
    if (isNaN(maxRetries) || maxRetries < 0) return { error: 'max_retries має бути ≥ 0' };
    if (isNaN(backoff) || backoff < 1)       return { error: 'retry_backoff має бути ≥ 1' };
    if (timeout !== null && timeout < 1)     return { error: 'timeout має бути ≥ 1' };

    const structured = {};
    if (spec.paramsStoreKey && storeId) structured[spec.paramsStoreKey] = storeId;
    if (spec.paramsCatKey   && catId)   structured[spec.paramsCatKey]   = catId;

    let extra = {};
    const raw = document.getElementById('schJobParamsJson').value.trim();
    if (raw) { try { extra = JSON.parse(raw); } catch { return { error: 'Невірний JSON у розширених параметрах' }; } }

    const finalParams = (Object.keys(structured).length || Object.keys(extra).length)
        ? { ...structured, ...extra } : null;

    return {
        payload: {
            source_key: sourceKey, runner_type: runnerType,
            enabled: document.getElementById('schJobEnabled').checked,
            allow_overlap: document.getElementById('schJobAllowOverlap').checked,
            max_retries: maxRetries, retry_backoff_sec: backoff,
            timeout_sec: timeout, params_json: finalParams,
        },
    };
}

// ── Schedule form — conditional field visibility ──────────────────────

function schToggleSchedFields(type) {
    document.getElementById('schSchedIntervalGroup').classList.toggle('hidden', type !== 'interval');
    document.getElementById('schSchedCronGroup').classList.toggle('hidden', type !== 'cron');
    const h = document.getElementById('schScedTypeHelp'); // NB: schScedTypeHelp uses 1-d in the HTML
    if (h) h.textContent = type === 'interval'
        ? 'Запускати через рівні проміжки часу.'
        : 'Запускати за cron-розкладом (час у зазначеній timezone).';
}

