/* service.scheduler.js — Scheduler tab (UI Polish wave, Commits 1-10) */
'use strict';

if (!document.getElementById('tab-scheduler')) { /* not this page */ }
else {

// ═══════════════════════════════════════════════════════════════════════
// Commit 1 — Runner metadata map
// ═══════════════════════════════════════════════════════════════════════

const RUNNER_SPECS = {
    store_category_sync: {
        label: 'Синхронізація категорій магазину',
        requiresStore: true, requiresCategory: false,
        storeHelp: 'Магазин, категорії якого синхронізувати',
        paramsStoreKey: 'store_id', paramsCatKey: null,
    },
    category_product_sync: {
        label: 'Синхронізація товарів категорії',
        requiresStore: true, requiresCategory: true,
        storeHelp: 'Магазин, що містить категорію',
        categoryHelp: 'Категорія для синхронізації товарів',
        paramsStoreKey: 'store_id', paramsCatKey: 'category_id',
    },
    all_stores_category_sync: {
        label: 'Синхронізація категорій всіх магазинів',
        requiresStore: false, requiresCategory: false,
        paramsStoreKey: null, paramsCatKey: null,
    },
};

function getRunnerUiSpec(rt) {
    return RUNNER_SPECS[rt] || { label: rt, requiresStore: false, requiresCategory: false, paramsStoreKey: null, paramsCatKey: null };
}
function runnerRequiresStore(rt)    { return !!getRunnerUiSpec(rt).requiresStore; }
function runnerRequiresCategory(rt) { return !!getRunnerUiSpec(rt).requiresCategory; }

// ═══════════════════════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════════════════════

const schState = {
    jobs: [], selectedJobId: null, selectedJob: null,
    selectedSchedule: null, jobModalMode: 'create',
    refData: { stores: null, categories: {}, loadingStores: false, loadingCats: {} },
};

// ═══════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════

function schSetStatus(msg, type = 'info') {
    const el = document.getElementById('schGlobalStatus');
    if (!el) return;
    el.textContent = msg; el.className = `status-pill status-${type}`;
    el.style.display = msg ? '' : 'none';
}
function schFmtDate(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleString('uk-UA'); } catch { return iso; }
}
function schFmtInterval(sec) {
    if (!sec) return '—';
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
    if (h) return `${h}г ${m}хв`; if (m) return `${m}хв ${s}с`; return `${s}с`;
}
function schStatusCls(st) {
    return ({queued:'info',running:'warning',success:'success',finished:'success',
             partial:'warning',failed:'error',skipped:'info',cancelled:'info',retry:'warning'})[st?.toLowerCase()] || 'info';
}
function schStatusLabel(st) {
    return ({queued:'🕒 queued',running:'⚙ running',success:'✓ success',finished:'✓ finished',
             partial:'⚠ partial',failed:'✗ failed',skipped:'⊘ skipped',cancelled:'⊝ cancelled',retry:'🔄 retry'})[st?.toLowerCase()] || (st||'—');
}
function schTriggerLabel(t) {
    return ({manual:'🖱 manual',scheduled:'⏱ scheduled',retry:'🔄 retry'})[t] || (t||'—');
}
function schInfoRow(label, value) {
    return `<div class="sch-info-row"><span class="sch-info-label">${label}</span><span class="sch-info-value">${value}</span></div>`;
}
function schShowError(elId, msg) {
    const el = document.getElementById(elId); if (!el) return;
    el.textContent = msg; el.classList.toggle('hidden', !msg);
}
function _storeName(id) {
    if (!id || !schState.refData.stores) return `#${id||'—'}`;
    const s = schState.refData.stores.find(x=>x.id===id);
    return s ? escHtml(s.name) : `#${id}`;
}
function _catName(catId, storeId) {
    if (!catId) return '—';
    const c = (schState.refData.categories[storeId]||[]).find(x=>x.id===catId);
    return c ? escHtml(c.name) : `#${catId}`;
}

// ═══════════════════════════════════════════════════════════════════════
// Commit 3 — Reference data loaders
// ═══════════════════════════════════════════════════════════════════════

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
        stores.map(s=>`<option value="${s.id}" ${s.id==sel?'selected':''}>${escHtml(s.name)}${s.is_reference?' ★':''}</option>`).join('');
}
function _buildCatOptions(storeId, sel) {
    const cats = schState.refData.categories[storeId] || [];
    if (!cats.length) return '<option value="">Немає категорій</option>';
    return '<option value="">— оберіть категорію —</option>' +
        cats.map(c=>`<option value="${c.id}" ${c.id==sel?'selected':''}>${escHtml(c.name)}</option>`).join('');
}

// ═══════════════════════════════════════════════════════════════════════
// Jobs list + loading
// ═══════════════════════════════════════════════════════════════════════

async function schLoadJobs() {
    schSetStatus('Завантаження…', 'info');
    await schLoadStores();
    try {
        const d = await fetchJson('/api/admin/scrape/jobs');
        schState.jobs = d.jobs || [];
        schRenderJobsList();
        schSetStatus(`Jobs: ${schState.jobs.length}`, schState.jobs.length ? 'success' : 'info');
        if (schState.selectedJobId && schState.jobs.find(j=>j.id===schState.selectedJobId))
            schSelectJob(schState.selectedJobId);
    } catch (err) {
        schSetStatus('Помилка: ' + err.message, 'error');
        document.getElementById('schJobsList').innerHTML = `<p class="muted sch-empty">Помилка: ${escHtml(err.message)}</p>`;
    }
}

// Commit 10 — richer list items
function schRenderJobsList() {
    const container = document.getElementById('schJobsList');
    if (!schState.jobs.length) {
        container.innerHTML = `<div class="sch-empty-list">
            <div class="sch-empty-icon">📋</div>
            <p class="muted">Немає scrape jobs.<br>Натисніть <strong>+ Новий job</strong> щоб створити перший.</p>
        </div>`;
        return;
    }
    container.innerHTML = schState.jobs.map(j => {
        const active   = j.id === schState.selectedJobId ? ' selected' : '';
        const eCls     = j.enabled ? 'sch-badge-enabled' : 'sch-badge-disabled';
        const spec     = getRunnerUiSpec(j.runner_type);
        const next     = j.next_run_at ? schFmtDate(j.next_run_at) : '—';
        const storeId  = j.params_json && j.params_json.store_id;
        const storeTxt = storeId ? `🏪 ${_storeName(storeId)}` : '';
        const hints    = [
            j.max_retries > 0 ? `<span class="sch-list-hint" title="retries">↺×${j.max_retries}</span>` : '',
            j.allow_overlap   ? `<span class="sch-list-hint" title="overlap OK">⟳</span>` : '',
        ].join('');
        return `<div class="sch-job-item${active}" data-id="${j.id}">
            <div class="sch-job-item-top">
                <span class="sch-job-source">${escHtml(j.source_key)}</span>
                <span class="sch-badge ${eCls}">${j.enabled?'ON':'OFF'}</span>
            </div>
            <div class="sch-job-item-sub">${escHtml(spec.label)}</div>
            ${storeTxt ? `<div class="sch-job-item-store">${storeTxt}</div>` : ''}
            <div class="sch-job-item-next"><span>▶ ${next}</span><span>${hints}</span></div>
        </div>`;
    }).join('');
    container.querySelectorAll('.sch-job-item').forEach(el =>
        el.addEventListener('click', () => schSelectJob(Number(el.dataset.id))));
}

// ═══════════════════════════════════════════════════════════════════════
// Job selection
// ═══════════════════════════════════════════════════════════════════════

async function schSelectJob(jobId) {
    schState.selectedJobId = jobId;
    document.querySelectorAll('.sch-job-item').forEach(el =>
        el.classList.toggle('selected', Number(el.dataset.id) === jobId));
    try {
        const d = await fetchJson(`/api/admin/scrape/jobs/${jobId}`);
        schState.selectedJob      = d.job;
        schState.selectedSchedule = d.schedules && d.schedules.length ? d.schedules[0] : null;
        const job = schState.selectedJob;
        if (job?.params_json?.store_id) await schLoadCategories(job.params_json.store_id);
        schRenderJobDetail();
        schLoadJobRuns(jobId);
    } catch (err) { schSetStatus('Помилка job: ' + err.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════════════
// Commit 8 — Structured detail panel
// ═══════════════════════════════════════════════════════════════════════

function schRenderJobDetail() {
    const job = schState.selectedJob; if (!job) return;
    document.getElementById('schNoSelection').classList.add('hidden');
    document.getElementById('schJobDetail').classList.remove('hidden');
    document.getElementById('schJobTitle').textContent = job.source_key;
    const badge = document.getElementById('schJobEnabledBadge');
    badge.textContent = job.enabled ? 'Активний' : 'Вимкнений';
    badge.className   = `status-pill status-${job.enabled ? 'success' : 'error'}`;
    document.getElementById('schToggleEnableBtn').textContent = job.enabled ? '⏸ Вимкнути' : '▶ Увімкнути';

    const spec    = getRunnerUiSpec(job.runner_type);
    const storeId = job.params_json?.store_id;
    const catId   = job.params_json?.category_id;

    const rows = [
        schInfoRow('Runner', `<span class="sch-runner-label">${escHtml(spec.label)}</span>`),
    ];
    if (spec.requiresStore)    rows.push(schInfoRow('Магазин',   storeId ? _storeName(storeId) : '<span class="muted">не вказано</span>'));
    if (spec.requiresCategory) rows.push(schInfoRow('Категорія', catId   ? _catName(catId, storeId) : '<span class="muted">не вказано</span>'));
    rows.push(
        schInfoRow('allow_overlap', job.allow_overlap ? '<span class="sch-badge sch-badge-overlap">так</span>' : '<span class="muted">ні</span>'),
        schInfoRow('max_retries',   job.max_retries > 0 ? `<span class="sch-badge sch-badge-retry">↺ ${job.max_retries}</span>` : '<span class="muted">0</span>'),
        schInfoRow('retry_backoff', schFmtInterval(job.retry_backoff_sec)),
        schInfoRow('timeout',       job.timeout_sec ? schFmtInterval(job.timeout_sec) : '<span class="muted">без обмеження</span>'),
        schInfoRow('Наступний запуск', schFmtDate(job.next_run_at)),
        schInfoRow('Останній запуск',  schFmtDate(job.last_run_at)),
    );

    const knownKeys = new Set(['store_id','category_id']);
    const extra = job.params_json ? Object.fromEntries(Object.entries(job.params_json).filter(([k])=>!knownKeys.has(k))) : null;
    const extraBlock = extra && Object.keys(extra).length
        ? `<details class="sch-advanced-block"><summary>▸ Додаткові params</summary><code class="sch-params-code">${escHtml(JSON.stringify(extra,null,2))}</code></details>` : '';

    document.getElementById('schJobFields').innerHTML = rows.join('') + extraBlock;
    schRenderSchedule(schState.selectedSchedule);
    const s = document.getElementById('schRunNowStatus'); s.style.display = 'none';
}

// Commit 7 — improved schedule card
function schRenderSchedule(sched) {
    const el = document.getElementById('schScheduleFields');
    if (!sched) {
        el.innerHTML = `<div class="sch-no-schedule"><span class="muted">Розклад не налаштовано</span></div>`;
        return;
    }
    const rows = [schInfoRow('Тип', sched.schedule_type === 'interval' ? '⏱ Інтервал' : '🗓 Cron')];
    if (sched.schedule_type === 'interval') rows.push(schInfoRow('Кожні', schFmtInterval(sched.interval_sec)));
    else if (sched.schedule_type === 'cron') {
        rows.push(schInfoRow('Cron', `<code class="sch-cron-code">${escHtml(sched.cron_expr||'—')}</code>`));
        rows.push(schInfoRow('Timezone', escHtml(sched.timezone||'UTC')));
    }
    if (sched.jitter_sec) rows.push(schInfoRow('Jitter', schFmtInterval(sched.jitter_sec)));
    rows.push(schInfoRow('Misfire', escHtml(sched.misfire_policy||'skip')));
    rows.push(schInfoRow('Статус', sched.enabled
        ? '<span class="sch-badge sch-badge-enabled">увімк</span>'
        : '<span class="sch-badge sch-badge-disabled">вимк</span>'));
    el.innerHTML = rows.join('');
}

// ═══════════════════════════════════════════════════════════════════════
// Runs table
// ═══════════════════════════════════════════════════════════════════════

async function schLoadJobRuns(jobId) {
    const c = document.getElementById('schRunsTable');
    c.innerHTML = '<p class="muted sch-empty">Завантаження…</p>';
    try {
        const d = await fetchJson(`/api/admin/scrape/jobs/${jobId}/runs?limit=20`);
        schRenderRunsTable(d.runs || []);
    } catch (err) { c.innerHTML = `<p class="muted sch-empty">Помилка: ${escHtml(err.message)}</p>`; }
}

function schRenderRunsTable(runs) {
    const c = document.getElementById('schRunsTable');
    if (!runs.length) { c.innerHTML = '<p class="muted sch-empty">Запусків ще не було</p>'; return; }
    const rows = runs.map(r => {
        const retryBadge = r.retryable && r.status==='failed'
            ? '<span class="sch-badge sch-badge-retry" title="Буде повторено">↺</span>' : '';
        const errRow = r.error_message
            ? `<tr class="sch-err-row"><td colspan="6"><div class="sch-run-error" title="${escHtml(r.error_message)}">✗ ${escHtml(r.error_message.slice(0,140))}${r.error_message.length>140?'…':''}</div></td></tr>` : '';
        return `<tr>
            <td>${schFmtDate(r.queued_at||r.started_at)}</td>
            <td>${schTriggerLabel(r.trigger_type)}</td>
            <td><span class="sch-attempt-badge">#${r.attempt||1}</span></td>
            <td><span class="status-pill status-${schStatusCls(r.status)}">${schStatusLabel(r.status)}</span>${retryBadge}</td>
            <td class="sch-worker-cell">${escHtml(r.worker_id||'—')}</td>
            <td><button class="ghost small" data-rid="${r.id}" title="Деталі">↗</button></td>
        </tr>${errRow}`;
    }).join('');
    c.innerHTML = `<table class="sch-runs-table">
        <thead><tr><th>Старт</th><th>Тригер</th><th>Спроба</th><th>Статус</th><th>Worker</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    c.querySelectorAll('button[data-rid]').forEach(btn =>
        btn.addEventListener('click', () => showRunDetails(Number(btn.dataset.rid))));
}

// ═══════════════════════════════════════════════════════════════════════
// Run now / Toggle
// ═══════════════════════════════════════════════════════════════════════

async function schRunNow() {
    const jobId = schState.selectedJobId; if (!jobId) return;
    const btn = document.getElementById('schRunNowBtn');
    const statusEl = document.getElementById('schRunNowStatus');
    btn.disabled = true; statusEl.style.display = '';
    statusEl.textContent = 'Запускаємо…'; statusEl.className = 'status-pill status-warning';
    try {
        const d = await fetchJson(`/api/admin/scrape/jobs/${jobId}/run`, {method:'POST'});
        statusEl.textContent = `Run #${d.run.id} поставлено в чергу`; statusEl.className = 'status-pill status-success';
        schLoadJobRuns(jobId); setTimeout(()=>{ statusEl.style.display='none'; }, 5000);
    } catch (err) {
        statusEl.textContent = err.status===409 || err.message?.includes('409')
            ? '⚠ Overlap: вже є активний запуск. Дочекайтесь або увімкніть allow_overlap.'
            : 'Помилка: ' + err.message;
        statusEl.className = 'status-pill status-error';
    } finally { btn.disabled = false; }
}

async function schToggleEnable() {
    const job = schState.selectedJob; if (!job) return;
    try {
        await fetchJson(`/api/admin/scrape/jobs/${job.id}`, {
            method:'PATCH', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({enabled: !job.enabled}),
        });
        await schLoadJobs();
    } catch (err) { schSetStatus('Помилка: '+err.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════════════
// Commits 4 — Runner-aware field visibility
// ═══════════════════════════════════════════════════════════════════════

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

// ═══════════════════════════════════════════════════════════════════════
// Commit 5 — Deserialize params_json → form
// ═══════════════════════════════════════════════════════════════════════

function _hydrateJobForm(job) {
    const p = job.params_json || {};
    const knownKeys = new Set(['store_id','category_id']);
    const extra = Object.fromEntries(Object.entries(p).filter(([k])=>!knownKeys.has(k)));
    document.getElementById('schJobSourceKey').value      = job.source_key || '';
    document.getElementById('schJobSourceKey').disabled   = true;
    document.getElementById('schJobRunnerType').value     = job.runner_type || 'store_category_sync';
    document.getElementById('schJobEnabled').checked      = !!job.enabled;
    document.getElementById('schJobAllowOverlap').checked = !!job.allow_overlap;
    document.getElementById('schJobMaxRetries').value     = job.max_retries ?? 0;
    document.getElementById('schJobRetryBackoff').value   = job.retry_backoff_sec ?? 60;
    document.getElementById('schJobTimeoutSec').value     = job.timeout_sec || '';
    document.getElementById('schJobParamsJson').value     = Object.keys(extra).length ? JSON.stringify(extra,null,2) : '';
    return { storeId: p.store_id||null, catId: p.category_id||null };
}

async function schOpenCreateJobModal() {
    schState.jobModalMode = 'create';
    document.getElementById('schJobModalTitle').textContent = 'Новий Scrape Job';
    document.getElementById('schJobSourceKey').value    = '';
    document.getElementById('schJobSourceKey').disabled = false;
    document.getElementById('schJobRunnerType').value   = 'store_category_sync';
    document.getElementById('schJobEnabled').checked    = true;
    document.getElementById('schJobAllowOverlap').checked = false;
    document.getElementById('schJobMaxRetries').value   = '0';
    document.getElementById('schJobRetryBackoff').value = '60';
    document.getElementById('schJobTimeoutSec').value   = '';
    document.getElementById('schJobParamsJson').value   = '';
    schShowError('schJobFormError',''); schShowError('schJobParamsJsonError','');
    await schUpdateRunnerFields('store_category_sync', null, null);
    document.getElementById('schJobModal').showModal();
}

async function schOpenEditJobModal() {
    const job = schState.selectedJob; if (!job) return;
    schState.jobModalMode = 'edit';
    document.getElementById('schJobModalTitle').textContent = 'Редагувати Job';
    schShowError('schJobFormError',''); schShowError('schJobParamsJsonError','');
    const {storeId, catId} = _hydrateJobForm(job);
    await schUpdateRunnerFields(job.runner_type, storeId, catId);
    document.getElementById('schJobModal').showModal();
}

// ═══════════════════════════════════════════════════════════════════════
// Commits 6 + 9 — Serialize form → payload with validation
// ═══════════════════════════════════════════════════════════════════════

function _serializeJobForm() {
    const runnerType = document.getElementById('schJobRunnerType').value;
    const spec       = getRunnerUiSpec(runnerType);
    const sourceKey  = document.getElementById('schJobSourceKey').value.trim();
    if (!sourceKey) return {error: "Source key є обов'язковим"};

    const storeId = parseInt(document.getElementById('schJobStoreId')?.value) || null;
    const catId   = parseInt(document.getElementById('schJobCategoryId')?.value) || null;
    if (spec.requiresStore    && !storeId) return {error: 'Оберіть магазин'};
    if (spec.requiresCategory && !catId)   return {error: 'Оберіть категорію'};

    const maxRetries = parseInt(document.getElementById('schJobMaxRetries').value);
    const backoff    = parseInt(document.getElementById('schJobRetryBackoff').value);
    const timeout    = parseInt(document.getElementById('schJobTimeoutSec').value) || null;
    if (isNaN(maxRetries)||maxRetries<0) return {error:'max_retries має бути ≥ 0'};
    if (isNaN(backoff)||backoff<1)       return {error:'retry_backoff має бути ≥ 1'};
    if (timeout!==null&&timeout<1)       return {error:'timeout має бути ≥ 1'};

    const structured = {};
    if (spec.paramsStoreKey && storeId) structured[spec.paramsStoreKey] = storeId;
    if (spec.paramsCatKey   && catId)   structured[spec.paramsCatKey]   = catId;

    let extra = {};
    const raw = document.getElementById('schJobParamsJson').value.trim();
    if (raw) { try { extra = JSON.parse(raw); } catch { return {error:'Невірний JSON у розширених параметрах'}; } }

    const finalParams = (Object.keys(structured).length || Object.keys(extra).length)
        ? {...structured, ...extra} : null;

    return {payload: {
        source_key: sourceKey, runner_type: runnerType,
        enabled: document.getElementById('schJobEnabled').checked,
        allow_overlap: document.getElementById('schJobAllowOverlap').checked,
        max_retries: maxRetries, retry_backoff_sec: backoff,
        timeout_sec: timeout, params_json: finalParams,
    }};
}

async function schSubmitJobForm(e) {
    e.preventDefault();
    schShowError('schJobFormError',''); schShowError('schJobParamsJsonError','');
    const result = _serializeJobForm();
    if (result.error) { schShowError('schJobFormError', result.error); return; }
    const btn = document.getElementById('schJobSubmit');
    btn.disabled = true; btn.textContent = 'Збереження…';
    try {
        if (schState.jobModalMode === 'create') {
            const d = await fetchJson('/api/admin/scrape/jobs', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify(result.payload),
            });
            document.getElementById('schJobModal').close();
            await schLoadJobs(); if (d.job) schSelectJob(d.job.id);
        } else {
            const jobId = schState.selectedJob.id;
            const patch = {...result.payload}; delete patch.source_key; delete patch.runner_type;
            await fetchJson(`/api/admin/scrape/jobs/${jobId}`, {
                method:'PATCH', headers:{'Content-Type':'application/json'},
                body: JSON.stringify(patch),
            });
            document.getElementById('schJobModal').close();
            await schLoadJobs(); schSelectJob(jobId);
        }
    } catch (err) { schShowError('schJobFormError', 'Помилка: '+err.message); }
    finally { btn.disabled=false; btn.textContent='Зберегти'; }
}

// ═══════════════════════════════════════════════════════════════════════
// Commit 7 — Schedule modal with conditional fields + validation
// ═══════════════════════════════════════════════════════════════════════

function schToggleSchedFields(type) {
    document.getElementById('schSchedIntervalGroup').classList.toggle('hidden', type!=='interval');
    document.getElementById('schSchedCronGroup').classList.toggle('hidden', type!=='cron');
    const h = document.getElementById('schScedTypeHelp');
    if (h) h.textContent = type==='interval'
        ? 'Запускати через рівні проміжки часу.'
        : 'Запускати за cron-розкладом (час у зазначеній timezone).';
}

function schOpenScheduleModal() {
    const sched = schState.selectedSchedule;
    document.getElementById('schScheduleModalTitle').textContent = sched ? 'Редагувати розклад' : 'Створити розклад';
    const type = sched?.schedule_type || 'interval';
    document.getElementById('schSchedType').value        = type;
    document.getElementById('schSchedIntervalSec').value = sched?.interval_sec || 3600;
    document.getElementById('schSchedCronExpr').value    = sched?.cron_expr || '';
    document.getElementById('schSchedTimezone').value    = sched?.timezone || 'UTC';
    document.getElementById('schSchedJitter').value      = sched?.jitter_sec || 0;
    document.getElementById('schSchedMisfire').value     = sched?.misfire_policy || 'skip';
    document.getElementById('schSchedEnabled').checked   = sched ? !!sched.enabled : true;
    schToggleSchedFields(type);
    schShowError('schScheduleFormError','');
    document.getElementById('schScheduleModal').showModal();
}

async function schSubmitScheduleForm(e) {
    e.preventDefault(); schShowError('schScheduleFormError','');
    const jobId = schState.selectedJobId; if (!jobId) return;
    const type = document.getElementById('schSchedType').value;
    const payload = {
        schedule_type: type,
        enabled:        document.getElementById('schSchedEnabled').checked,
        jitter_sec:     parseInt(document.getElementById('schSchedJitter').value)||0,
        misfire_policy: document.getElementById('schSchedMisfire').value,
    };
    if (type==='interval') {
        const sec = parseInt(document.getElementById('schSchedIntervalSec').value);
        if (!sec||sec<60) { schShowError('schScheduleFormError','Інтервал має бути не менше 60 секунд'); return; }
        payload.interval_sec = sec;
    } else if (type==='cron') {
        const expr = document.getElementById('schSchedCronExpr').value.trim();
        const tz   = document.getElementById('schSchedTimezone').value.trim()||'UTC';
        if (!expr) { schShowError('schScheduleFormError','Введіть cron вираз (наприклад: 0 9 * * 1-5)'); return; }
        if (expr.split(/\s+/).length!==5) { schShowError('schScheduleFormError','Cron вираз: 5 полів (хв год д-м міс д-тижня)'); return; }
        payload.cron_expr = expr; payload.timezone = tz;
    }
    const btns = document.querySelectorAll('#schScheduleForm button[type=submit]');
    btns.forEach(b=>{ b.disabled=true; b.textContent='Збереження…'; });
    try {
        const d = await fetchJson(`/api/admin/scrape/jobs/${jobId}/schedule`, {
            method:'PUT', headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload),
        });
        document.getElementById('schScheduleModal').close();
        schState.selectedSchedule = d.schedule;
        schRenderSchedule(d.schedule);
        await schLoadJobs();
    } catch (err) { schShowError('schScheduleFormError', 'Помилка: '+(err.responseBody||err.message)); }
    finally { btns.forEach(b=>{ b.disabled=false; b.textContent='Зберегти'; }); }
}

// ═══════════════════════════════════════════════════════════════════════
// Event wiring
// ═══════════════════════════════════════════════════════════════════════

document.getElementById('schCreateJobBtn').addEventListener('click', schOpenCreateJobModal);
document.getElementById('schRefreshBtn').addEventListener('click', schLoadJobs);
document.getElementById('schRunNowBtn').addEventListener('click', schRunNow);
document.getElementById('schToggleEnableBtn').addEventListener('click', schToggleEnable);
document.getElementById('schEditJobBtn').addEventListener('click', schOpenEditJobModal);
document.getElementById('schEditScheduleBtn').addEventListener('click', schOpenScheduleModal);
document.getElementById('schRefreshRunsBtn').addEventListener('click', ()=>{ if(schState.selectedJobId) schLoadJobRuns(schState.selectedJobId); });

document.getElementById('schJobForm').addEventListener('submit', schSubmitJobForm);
document.getElementById('schJobCancel').addEventListener('click', ()=>document.getElementById('schJobModal').close());

// Commit 4 — runner type → field visibility
document.getElementById('schJobRunnerType').addEventListener('change', async e=>{
    const storeId = parseInt(document.getElementById('schJobStoreId')?.value)||null;
    const catId   = parseInt(document.getElementById('schJobCategoryId')?.value)||null;
    await schUpdateRunnerFields(e.target.value, storeId, catId);
});
// Commit 4 — store change → reload categories
document.addEventListener('change', async e=>{
    if (e.target.id!=='schJobStoreId') return;
    const rt = document.getElementById('schJobRunnerType').value;
    if (!runnerRequiresCategory(rt)) return;
    const storeId = parseInt(e.target.value)||null;
    if (!storeId) return;
    await schLoadCategories(storeId);
    const catSel = document.getElementById('schJobCategoryId');
    if (catSel) { catSel.innerHTML = _buildCatOptions(storeId, null); catSel.required = true; }
});

document.getElementById('schScheduleForm').addEventListener('submit', schSubmitScheduleForm);
document.getElementById('schScheduleCancel').addEventListener('click', ()=>document.getElementById('schScheduleModal').close());
document.getElementById('schSchedType').addEventListener('change', e=>schToggleSchedFields(e.target.value));

// Patch fetchJson for HTTP status
(function patchFetchJson(){
    const _orig = window.fetchJson; if(!_orig) return;
    window.fetchJson = async function(url, opts){
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            let msg; try { const j=await resp.json(); msg=j.message||j.error||resp.statusText; } catch { msg=resp.statusText; }
            const err=new Error(`${resp.status}: ${msg}`); err.status=resp.status; err.responseBody=msg; throw err;
        }
        return resp.json();
    };
})();

window.schLoadJobs = schLoadJobs;

} // end guard

