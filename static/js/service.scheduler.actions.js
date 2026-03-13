/* service.scheduler.actions.js — Scheduler user-triggered workflows and event wiring */
'use strict';

// ── Load / refresh workflows ──────────────────────────────────────────

async function schLoadJobs() {
    schSetStatus('Завантаження…', 'info');
    await schLoadStores();
    try {
        const d = await schApiLoadJobs();
        schState.jobs = d.jobs || [];
        schRenderJobsList();
        schSetStatus(`Jobs: ${schState.jobs.length}`, schState.jobs.length ? 'success' : 'info');
        if (schState.selectedJobId && schState.jobs.find(j => j.id === schState.selectedJobId))
            schSelectJob(schState.selectedJobId);
    } catch (err) {
        schSetStatus('Помилка: ' + err.message, 'error');
        document.getElementById('schJobsList').innerHTML = `<p class="muted sch-empty">Помилка: ${escHtml(err.message)}</p>`;
    }
}

async function schLoadJobRuns(jobId) {
    const c = document.getElementById('schRunsTable');
    c.innerHTML = '<p class="muted sch-empty">Завантаження…</p>';
    try {
        const d = await schApiLoadJobRuns(jobId);
        schRenderRunsTable(d.runs || []);
    } catch (err) { c.innerHTML = `<p class="muted sch-empty">Помилка: ${escHtml(err.message)}</p>`; }
}

// ── Job selection ─────────────────────────────────────────────────────

async function schSelectJob(jobId) {
    schState.selectedJobId = jobId;
    document.querySelectorAll('.sch-job-item').forEach(el =>
        el.classList.toggle('selected', Number(el.dataset.id) === jobId));
    try {
        const d = await schApiLoadJobDetail(jobId);
        schState.selectedJob      = d.job;
        schState.selectedSchedule = d.schedules && d.schedules.length ? d.schedules[0] : null;
        const job = schState.selectedJob;
        if (job?.params_json?.store_id) await schLoadCategories(job.params_json.store_id);
        schRenderJobDetail();
        schLoadJobRuns(jobId);
    } catch (err) { schSetStatus('Помилка job: ' + err.message, 'error'); }
}

// ── Job modal actions ─────────────────────────────────────────────────

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
    schShowError('schJobFormError', ''); schShowError('schJobParamsJsonError', '');
    await schUpdateRunnerFields('store_category_sync', null, null);
    document.getElementById('schJobModal').showModal();
}

async function schOpenEditJobModal() {
    const job = schState.selectedJob; if (!job) return;
    schState.jobModalMode = 'edit';
    document.getElementById('schJobModalTitle').textContent = 'Редагувати Job';
    schShowError('schJobFormError', ''); schShowError('schJobParamsJsonError', '');
    const { storeId, catId } = _hydrateJobForm(job);
    await schUpdateRunnerFields(job.runner_type, storeId, catId);
    document.getElementById('schJobModal').showModal();
}

async function schSubmitJobForm(e) {
    e.preventDefault();
    schShowError('schJobFormError', ''); schShowError('schJobParamsJsonError', '');
    const result = _serializeJobForm();
    if (result.error) { schShowError('schJobFormError', result.error); return; }
    const btn = document.getElementById('schJobSubmit');
    btn.disabled = true; btn.textContent = 'Збереження…';
    try {
        if (schState.jobModalMode === 'create') {
            const d = await schApiCreateJob(result.payload);
            document.getElementById('schJobModal').close();
            await schLoadJobs(); if (d.job) schSelectJob(d.job.id);
        } else {
            const jobId = schState.selectedJob.id;
            const patch = { ...result.payload }; delete patch.source_key; delete patch.runner_type;
            await schApiUpdateJob(jobId, patch);
            document.getElementById('schJobModal').close();
            await schLoadJobs(); schSelectJob(jobId);
        }
    } catch (err) { schShowError('schJobFormError', 'Помилка: ' + err.message); }
    finally { btn.disabled = false; btn.textContent = 'Зберегти'; }
}

// ── Schedule modal actions ────────────────────────────────────────────

function schOpenScheduleModal() {
    const sched = schState.selectedSchedule;
    document.getElementById('schScheduleModalTitle').textContent = sched ? 'Редагувати розклад' : 'Створити розклад';
    const type = sched?.schedule_type || 'interval';
    document.getElementById('schScedType').value        = type;
    document.getElementById('schScedIntervalSec').value = sched?.interval_sec || 3600;
    document.getElementById('schScedCronExpr').value    = sched?.cron_expr || '';
    document.getElementById('schScedTimezone').value    = sched?.timezone || 'UTC';
    document.getElementById('schScedJitter').value      = sched?.jitter_sec || 0;
    document.getElementById('schScedMisfire').value     = sched?.misfire_policy || 'skip';
    document.getElementById('schScedEnabled').checked   = sched ? !!sched.enabled : true;
    schToggleSchedFields(type);
    schShowError('schScheduleFormError', '');
    document.getElementById('schScheduleModal').showModal();
}

async function schSubmitScheduleForm(e) {
    e.preventDefault(); schShowError('schScheduleFormError', '');
    const jobId = schState.selectedJobId; if (!jobId) return;
    const type = document.getElementById('schScedType').value;
    const payload = {
        schedule_type:  type,
        enabled:        document.getElementById('schScedEnabled').checked,
        jitter_sec:     parseInt(document.getElementById('schScedJitter').value) || 0,
        misfire_policy: document.getElementById('schScedMisfire').value,
    };
    if (type === 'interval') {
        const sec = parseInt(document.getElementById('schScedIntervalSec').value);
        if (!sec || sec < 60) { schShowError('schScheduleFormError', 'Інтервал має бути не менше 60 секунд'); return; }
        payload.interval_sec = sec;
    } else if (type === 'cron') {
        const expr = document.getElementById('schScedCronExpr').value.trim();
        const tz   = document.getElementById('schScedTimezone').value.trim() || 'UTC';
        if (!expr) { schShowError('schScheduleFormError', 'Введіть cron вираз (наприклад: 0 9 * * 1-5)'); return; }
        if (expr.split(/\s+/).length !== 5) { schShowError('schScheduleFormError', 'Cron вираз: 5 полів (хв год д-м міс д-тижня)'); return; }
        payload.cron_expr = expr; payload.timezone = tz;
    }
    const btns = document.querySelectorAll('#schScheduleForm button[type=submit]');
    btns.forEach(b => { b.disabled = true; b.textContent = 'Збереження…'; });
    try {
        const d = await schApiSaveSchedule(jobId, payload);
        document.getElementById('schScheduleModal').close();
        schState.selectedSchedule = d.schedule;
        schRenderSchedule(d.schedule);
        await schLoadJobs();
    } catch (err) { schShowError('schScheduleFormError', 'Помилка: ' + (err.responseBody || err.message)); }
    finally { btns.forEach(b => { b.disabled = false; b.textContent = 'Зберегти'; }); }
}

// ── Run-now / toggle enable ───────────────────────────────────────────

async function schRunNow() {
    const jobId = schState.selectedJobId; if (!jobId) return;
    const btn = document.getElementById('schRunNowBtn');
    const statusEl = document.getElementById('schRunNowStatus');
    btn.disabled = true; statusEl.style.display = '';
    statusEl.textContent = 'Запускаємо…'; statusEl.className = 'status-pill status-warning';
    try {
        const d = await schApiRunNow(jobId);
        statusEl.textContent = `Run #${d.run.id} поставлено в чергу`; statusEl.className = 'status-pill status-success';
        schLoadJobRuns(jobId); setTimeout(() => { statusEl.style.display = 'none'; }, 5000);
    } catch (err) {
        statusEl.textContent = err.status === 409 || err.message?.includes('409')
            ? '⚠ Overlap: вже є активний запуск. Дочекайтесь або увімкніть allow_overlap.'
            : 'Помилка: ' + err.message;
        statusEl.className = 'status-pill status-error';
    } finally { btn.disabled = false; }
}

async function schToggleEnable() {
    const job = schState.selectedJob; if (!job) return;
    try {
        await schApiToggleJob(job.id, !job.enabled);
        await schLoadJobs();
    } catch (err) { schSetStatus('Помилка: ' + err.message, 'error'); }
}

// ── Event wiring ──────────────────────────────────────────────────────

(function schWireEvents() {
    if (!document.getElementById('tab-scheduler')) return;

    document.getElementById('schCreateJobBtn').addEventListener('click', schOpenCreateJobModal);
    document.getElementById('schRefreshBtn').addEventListener('click', schLoadJobs);
    document.getElementById('schRunNowBtn').addEventListener('click', schRunNow);
    document.getElementById('schToggleEnableBtn').addEventListener('click', schToggleEnable);
    document.getElementById('schEditJobBtn').addEventListener('click', schOpenEditJobModal);
    document.getElementById('schEditScheduleBtn').addEventListener('click', schOpenScheduleModal);
    document.getElementById('schRefreshRunsBtn').addEventListener('click', () => {
        if (schState.selectedJobId) schLoadJobRuns(schState.selectedJobId);
    });

    document.getElementById('schJobForm').addEventListener('submit', schSubmitJobForm);
    document.getElementById('schJobCancel').addEventListener('click', () => document.getElementById('schJobModal').close());

    // Runner type → field visibility
    document.getElementById('schJobRunnerType').addEventListener('change', async e => {
        const storeId = parseInt(document.getElementById('schJobStoreId')?.value) || null;
        const catId   = parseInt(document.getElementById('schJobCategoryId')?.value) || null;
        await schUpdateRunnerFields(e.target.value, storeId, catId);
    });

    // Store change → reload categories
    document.addEventListener('change', async e => {
        if (e.target.id !== 'schJobStoreId') return;
        const rt = document.getElementById('schJobRunnerType').value;
        if (!runnerRequiresCategory(rt)) return;
        const storeId = parseInt(e.target.value) || null;
        if (!storeId) return;
        await schLoadCategories(storeId);
        const catSel = document.getElementById('schJobCategoryId');
        if (catSel) { catSel.innerHTML = _buildCatOptions(storeId, null); catSel.required = true; }
    });

    document.getElementById('schScheduleForm').addEventListener('submit', schSubmitScheduleForm);
    document.getElementById('schScheduleCancel').addEventListener('click', () => document.getElementById('schScheduleModal').close());
    document.getElementById('schScedType').addEventListener('change', e => schToggleSchedFields(e.target.value));
})();

