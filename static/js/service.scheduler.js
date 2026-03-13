/* service.scheduler.js — Scheduler tab logic for the Service Console
 *
 * Loaded after service.js. Exposes window.schLoadJobs so service.js
 * can call it when the Scheduler tab becomes active.
 *
 * API surface used:
 *   GET  /api/admin/scrape/jobs
 *   POST /api/admin/scrape/jobs
 *   GET  /api/admin/scrape/jobs/<id>
 *   PATCH /api/admin/scrape/jobs/<id>
 *   POST /api/admin/scrape/jobs/<id>/run
 *   GET  /api/admin/scrape/jobs/<id>/runs
 *   GET  /api/admin/scrape/jobs/<id>/schedule
 *   PUT  /api/admin/scrape/jobs/<id>/schedule
 */
'use strict';

// Guard — only run when the scheduler tab elements exist
if (!document.getElementById('tab-scheduler')) { /* not this page */ }
else {

// ── State ─────────────────────────────────────────────────────────────
const schState = {
    jobs: [],
    selectedJobId: null,
    selectedJob: null,
    selectedSchedule: null,
    jobModalMode: 'create', // 'create' | 'edit'
};

// ── Helpers ───────────────────────────────────────────────────────────
function schSetStatus(msg, type = 'info') {
    const el = document.getElementById('schGlobalStatus');
    if (!el) return;
    el.textContent = msg;
    el.className   = `status-pill status-${type}`;
    el.style.display = msg ? '' : 'none';
}

function schFmtDate(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function schStatusCls(status) {
    if (!status) return 'info';
    const m = {
        queued: 'info', running: 'warning', success: 'success',
        finished: 'success', partial: 'warning', failed: 'error',
        skipped: 'info', cancelled: 'info', retry: 'warning',
    };
    return m[status.toLowerCase()] || 'info';
}

function schStatusLabel(status) {
    if (!status) return '—';
    const m = {
        queued: '🕒 queued', running: '⚙ running', success: '✓ success',
        finished: '✓ finished', partial: '⚠ partial', failed: '✗ failed',
        skipped: '⊘ skipped', cancelled: '⊝ cancelled', retry: '🔄 retry',
    };
    return m[status.toLowerCase()] || status;
}

function schTriggerLabel(t) {
    if (!t) return '—';
    return { manual: '🖱 manual', scheduled: '⏱ scheduled', retry: '🔄 retry' }[t] || t;
}

function schInfoRow(label, value) {
    return `<div class="sch-info-row"><span class="sch-info-label">${label}</span><span class="sch-info-value">${value}</span></div>`;
}

function schShowError(elId, msg) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle('hidden', !msg);
}

// ── Jobs list ─────────────────────────────────────────────────────────
async function schLoadJobs() {
    schSetStatus('Завантаження…', 'info');
    try {
        const data = await fetchJson('/api/admin/scrape/jobs');
        schState.jobs = data.jobs || [];
        schRenderJobsList();
        schSetStatus(`Jobs: ${schState.jobs.length}`, schState.jobs.length ? 'success' : 'info');
        // Refresh selected job if still present
        if (schState.selectedJobId) {
            const still = schState.jobs.find(j => j.id === schState.selectedJobId);
            if (still) schSelectJob(still.id);
        }
    } catch (err) {
        schSetStatus('Помилка завантаження: ' + err.message, 'error');
        document.getElementById('schJobsList').innerHTML = `<p class="muted sch-empty">Помилка: ${escHtml(err.message)}</p>`;
    }
}

function schRenderJobsList() {
    const container = document.getElementById('schJobsList');
    if (!schState.jobs.length) {
        container.innerHTML = '<p class="muted sch-empty">Немає jobs. Створіть перший.</p>';
        return;
    }
    container.innerHTML = schState.jobs.map(j => {
        const active = j.id === schState.selectedJobId ? ' selected' : '';
        const eCls   = j.enabled ? 'sch-badge-enabled' : 'sch-badge-disabled';
        const eLabel = j.enabled ? 'ON' : 'OFF';
        const next   = j.next_run_at ? schFmtDate(j.next_run_at) : '—';
        return `<div class="sch-job-item${active}" data-id="${j.id}">
            <div class="sch-job-item-top">
                <span class="sch-job-source">${escHtml(j.source_key)}</span>
                <span class="sch-badge ${eCls}">${eLabel}</span>
            </div>
            <div class="sch-job-item-sub">${escHtml(j.runner_type)}</div>
            <div class="sch-job-item-next">▶ ${next}</div>
        </div>`;
    }).join('');
    container.querySelectorAll('.sch-job-item').forEach(el => {
        el.addEventListener('click', () => schSelectJob(Number(el.dataset.id)));
    });
}

// ── Job selection ─────────────────────────────────────────────────────
async function schSelectJob(jobId) {
    schState.selectedJobId = jobId;
    // Highlight in list
    document.querySelectorAll('.sch-job-item').forEach(el => {
        el.classList.toggle('selected', Number(el.dataset.id) === jobId);
    });
    // Load full job data
    try {
        const data = await fetchJson(`/api/admin/scrape/jobs/${jobId}`);
        schState.selectedJob      = data.job;
        schState.selectedSchedule = data.schedules && data.schedules.length ? data.schedules[0] : null;
        schRenderJobDetail();
        schLoadJobRuns(jobId);
    } catch (err) {
        schSetStatus('Помилка job: ' + err.message, 'error');
    }
}

function schRenderJobDetail() {
    const job = schState.selectedJob;
    if (!job) return;

    document.getElementById('schNoSelection').classList.add('hidden');
    document.getElementById('schJobDetail').classList.remove('hidden');

    // Title + badge
    document.getElementById('schJobTitle').textContent = job.source_key;
    const badge = document.getElementById('schJobEnabledBadge');
    badge.textContent = job.enabled ? 'Активний' : 'Вимкнений';
    badge.className   = `status-pill status-${job.enabled ? 'success' : 'error'}`;

    // Toggle button label
    document.getElementById('schToggleEnableBtn').textContent = job.enabled ? '⏸ Вимкнути' : '▶ Увімкнути';

    // Fields grid
    const params = job.params_json ? JSON.stringify(job.params_json) : '—';
    document.getElementById('schJobFields').innerHTML = [
        schInfoRow('Runner type',      escHtml(job.runner_type)),
        schInfoRow('allow_overlap',    job.allow_overlap ? 'так' : 'ні'),
        schInfoRow('max_retries',      job.max_retries ?? 0),
        schInfoRow('retry_backoff',    (job.retry_backoff_sec ?? 60) + ' сек'),
        schInfoRow('timeout',          job.timeout_sec ? job.timeout_sec + ' сек' : '—'),
        schInfoRow('priority',         job.priority ?? 0),
        schInfoRow('next_run_at',      schFmtDate(job.next_run_at)),
        schInfoRow('last_run_at',      schFmtDate(job.last_run_at)),
        schInfoRow('params',           `<code>${escHtml(params)}</code>`),
    ].join('');

    // Schedule
    schRenderSchedule(schState.selectedSchedule);

    // Clear run now status
    const s = document.getElementById('schRunNowStatus');
    s.style.display = 'none';
    s.textContent   = '';
}

function schRenderSchedule(sched) {
    const el = document.getElementById('schScheduleFields');
    if (!sched) {
        el.innerHTML = schInfoRow('Статус', '<span class="muted">Розклад не налаштовано</span>');
        return;
    }
    const rows = [
        schInfoRow('Тип',           escHtml(sched.schedule_type)),
        schInfoRow('enabled',       sched.enabled ? 'так' : 'ні'),
    ];
    if (sched.schedule_type === 'interval') {
        rows.push(schInfoRow('Інтервал', `${sched.interval_sec ?? '—'} сек`));
    } else if (sched.schedule_type === 'cron') {
        rows.push(schInfoRow('Cron', `<code>${escHtml(sched.cron_expr || '—')}</code>`));
        rows.push(schInfoRow('Timezone', escHtml(sched.timezone || 'UTC')));
    }
    rows.push(schInfoRow('Jitter',          (sched.jitter_sec ?? 0) + ' сек'));
    rows.push(schInfoRow('Misfire policy',  escHtml(sched.misfire_policy || 'skip')));
    el.innerHTML = rows.join('');
}

// ── Job runs ──────────────────────────────────────────────────────────
async function schLoadJobRuns(jobId) {
    const container = document.getElementById('schRunsTable');
    container.innerHTML = '<p class="muted sch-empty">Завантаження…</p>';
    try {
        const data = await fetchJson(`/api/admin/scrape/jobs/${jobId}/runs?limit=20`);
        schRenderRunsTable(data.runs || []);
    } catch (err) {
        container.innerHTML = `<p class="muted sch-empty">Помилка: ${escHtml(err.message)}</p>`;
    }
}

function schRenderRunsTable(runs) {
    const container = document.getElementById('schRunsTable');
    if (!runs.length) {
        container.innerHTML = '<p class="muted sch-empty">Запусків ще не було</p>';
        return;
    }
    const rows = runs.map(r => {
        const sCls    = schStatusCls(r.status);
        const sLabel  = schStatusLabel(r.status);
        const trigger = schTriggerLabel(r.trigger_type);
        const queued  = schFmtDate(r.queued_at || r.started_at);
        const finished = schFmtDate(r.finished_at);
        const retryBadge = r.retryable && r.status === 'failed'
            ? '<span class="sch-badge sch-badge-retry" title="Буде повторено">↺</span>' : '';
        const errSum = r.error_message
            ? `<div class="sch-run-error">${escHtml(r.error_message.slice(0, 120))}${r.error_message.length > 120 ? '…' : ''}</div>` : '';
        return `<tr>
            <td>${queued}</td>
            <td>${trigger}</td>
            <td><span class="sch-attempt-badge" title="спроба">#${r.attempt || 1}</span></td>
            <td><span class="status-pill status-${sCls}">${sLabel}</span>${retryBadge}</td>
            <td>${escHtml(r.worker_id || '—')}</td>
            <td><button class="ghost small" data-rid="${r.id}">↗</button></td>
        </tr>
        ${errSum ? `<tr class="sch-err-row"><td colspan="6">${errSum}</td></tr>` : ''}`;
    }).join('');
    container.innerHTML = `
        <table class="sch-runs-table">
            <thead><tr>
                <th>Старт</th><th>Тригер</th><th>Спроба</th>
                <th>Статус</th><th>Worker</th><th></th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
    container.querySelectorAll('button[data-rid]').forEach(btn => {
        btn.addEventListener('click', () => showRunDetails(Number(btn.dataset.rid)));
    });
}

// ── Actions: Run now ──────────────────────────────────────────────────
async function schRunNow() {
    const jobId = schState.selectedJobId;
    if (!jobId) return;
    const btn = document.getElementById('schRunNowBtn');
    const statusEl = document.getElementById('schRunNowStatus');
    btn.disabled = true;
    statusEl.style.display = '';
    statusEl.textContent   = 'Запускаємо…';
    statusEl.className     = 'status-pill status-warning';
    try {
        const data = await fetchJson(`/api/admin/scrape/jobs/${jobId}/run`, { method: 'POST' });
        statusEl.textContent = `Run #${data.run.id} поставлено в чергу`;
        statusEl.className   = 'status-pill status-success';
        schLoadJobRuns(jobId);
        setTimeout(() => { statusEl.style.display = 'none'; }, 5000);
    } catch (err) {
        // Decision 2: 409 Conflict must be visible
        if (err.status === 409 || (err.message && err.message.includes('409'))) {
            statusEl.textContent = '⚠ Overlap: вже є активний запуск. Дочекайтесь завершення або увімкніть allow_overlap.';
            statusEl.className   = 'status-pill status-error';
        } else {
            statusEl.textContent = 'Помилка: ' + err.message;
            statusEl.className   = 'status-pill status-error';
        }
    } finally {
        btn.disabled = false;
    }
}

// ── Actions: Toggle enable ────────────────────────────────────────────
async function schToggleEnable() {
    const job = schState.selectedJob;
    if (!job) return;
    const newEnabled = !job.enabled;
    try {
        await fetchJson(`/api/admin/scrape/jobs/${job.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: newEnabled }),
        });
        await schLoadJobs();
    } catch (err) {
        schSetStatus('Помилка: ' + err.message, 'error');
    }
}

// ── Job modal: create ─────────────────────────────────────────────────
function schOpenCreateJobModal() {
    schState.jobModalMode = 'create';
    document.getElementById('schJobModalTitle').textContent = 'Новий Scrape Job';
    document.getElementById('schJobSourceKey').value   = '';
    document.getElementById('schJobSourceKey').disabled = false;
    document.getElementById('schJobRunnerType').value  = 'store_category_sync';
    document.getElementById('schJobEnabled').checked   = true;
    document.getElementById('schJobAllowOverlap').checked = false;
    document.getElementById('schJobMaxRetries').value  = '0';
    document.getElementById('schJobRetryBackoff').value = '60';
    document.getElementById('schJobTimeoutSec').value  = '';
    document.getElementById('schJobParamsJson').value  = '';
    schShowError('schJobFormError', '');
    schShowError('schJobParamsJsonError', '');
    document.getElementById('schJobModal').showModal();
}

// ── Job modal: edit ───────────────────────────────────────────────────
function schOpenEditJobModal() {
    const job = schState.selectedJob;
    if (!job) return;
    schState.jobModalMode = 'edit';
    document.getElementById('schJobModalTitle').textContent = 'Редагувати Job';
    document.getElementById('schJobSourceKey').value   = job.source_key;
    document.getElementById('schJobSourceKey').disabled = true; // source_key immutable
    document.getElementById('schJobRunnerType').value  = job.runner_type;
    document.getElementById('schJobEnabled').checked   = !!job.enabled;
    document.getElementById('schJobAllowOverlap').checked = !!job.allow_overlap;
    document.getElementById('schJobMaxRetries').value  = job.max_retries ?? 0;
    document.getElementById('schJobRetryBackoff').value = job.retry_backoff_sec ?? 60;
    document.getElementById('schJobTimeoutSec').value  = job.timeout_sec || '';
    document.getElementById('schJobParamsJson').value  = job.params_json ? JSON.stringify(job.params_json, null, 2) : '';
    schShowError('schJobFormError', '');
    schShowError('schJobParamsJsonError', '');
    document.getElementById('schJobModal').showModal();
}

async function schSubmitJobForm(e) {
    e.preventDefault();
    schShowError('schJobFormError', '');
    schShowError('schJobParamsJsonError', '');

    const paramsRaw = document.getElementById('schJobParamsJson').value.trim();
    let paramsJson = null;
    if (paramsRaw) {
        try { paramsJson = JSON.parse(paramsRaw); }
        catch {
            schShowError('schJobParamsJsonError', 'Невірний JSON');
            return;
        }
    }

    const payload = {
        source_key:        document.getElementById('schJobSourceKey').value.trim(),
        runner_type:       document.getElementById('schJobRunnerType').value,
        enabled:           document.getElementById('schJobEnabled').checked,
        allow_overlap:     document.getElementById('schJobAllowOverlap').checked,
        max_retries:       parseInt(document.getElementById('schJobMaxRetries').value) || 0,
        retry_backoff_sec: parseInt(document.getElementById('schJobRetryBackoff').value) || 60,
        timeout_sec:       parseInt(document.getElementById('schJobTimeoutSec').value) || null,
        params_json:       paramsJson,
    };

    const submitBtn = document.getElementById('schJobSubmit');
    submitBtn.disabled = true;

    try {
        if (schState.jobModalMode === 'create') {
            const data = await fetchJson('/api/admin/scrape/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            document.getElementById('schJobModal').close();
            await schLoadJobs();
            if (data.job) schSelectJob(data.job.id);
        } else {
            const jobId = schState.selectedJob.id;
            // PATCH only updatable fields
            const patch = { ...payload };
            delete patch.source_key;
            delete patch.runner_type;
            await fetchJson(`/api/admin/scrape/jobs/${jobId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(patch),
            });
            document.getElementById('schJobModal').close();
            await schLoadJobs();
            schSelectJob(jobId);
        }
    } catch (err) {
        schShowError('schJobFormError', 'Помилка: ' + err.message);
    } finally {
        submitBtn.disabled = false;
    }
}

// ── Schedule modal ────────────────────────────────────────────────────
function schOpenScheduleModal() {
    const sched = schState.selectedSchedule;
    const title = sched ? 'Редагувати розклад' : 'Створити розклад';
    document.getElementById('schScheduleModalTitle').textContent = title;

    const type = sched ? sched.schedule_type : 'interval';
    document.getElementById('schSchedType').value        = type;
    document.getElementById('schSchedIntervalSec').value = sched ? (sched.interval_sec || 3600) : 3600;
    document.getElementById('schSchedCronExpr').value    = sched ? (sched.cron_expr || '') : '';
    document.getElementById('schSchedTimezone').value    = sched ? (sched.timezone || 'UTC') : 'UTC';
    document.getElementById('schSchedJitter').value      = sched ? (sched.jitter_sec || 0) : 0;
    document.getElementById('schSchedMisfire').value     = sched ? (sched.misfire_policy || 'skip') : 'skip';
    document.getElementById('schSchedEnabled').checked   = sched ? !!sched.enabled : true;

    schToggleSchedFields(type);
    schShowError('schScheduleFormError', '');
    document.getElementById('schScheduleModal').showModal();
}

function schToggleSchedFields(type) {
    document.getElementById('schSchedIntervalGroup').classList.toggle('hidden', type !== 'interval');
    document.getElementById('schSchedCronGroup').classList.toggle('hidden', type !== 'cron');
}

async function schSubmitScheduleForm(e) {
    e.preventDefault();
    schShowError('schScheduleFormError', '');
    const jobId = schState.selectedJobId;
    if (!jobId) return;

    const type = document.getElementById('schSchedType').value;
    const payload = {
        schedule_type: type,
        enabled:       document.getElementById('schSchedEnabled').checked,
        jitter_sec:    parseInt(document.getElementById('schSchedJitter').value) || 0,
        misfire_policy: document.getElementById('schSchedMisfire').value,
    };
    if (type === 'interval') {
        const sec = parseInt(document.getElementById('schSchedIntervalSec').value);
        if (!sec || sec < 60) {
            schShowError('schScheduleFormError', 'Інтервал має бути не менше 60 секунд');
            return;
        }
        payload.interval_sec = sec;
    } else if (type === 'cron') {
        const expr = document.getElementById('schSchedCronExpr').value.trim();
        const tz   = document.getElementById('schSchedTimezone').value.trim() || 'UTC';
        if (!expr) { schShowError('schScheduleFormError', 'Введіть cron вираз'); return; }
        payload.cron_expr = expr;
        payload.timezone  = tz;
    }

    try {
        const data = await fetchJson(`/api/admin/scrape/jobs/${jobId}/schedule`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        document.getElementById('schScheduleModal').close();
        schState.selectedSchedule = data.schedule;
        schRenderSchedule(data.schedule);
        // Refresh job to show updated next_run_at
        await schLoadJobs();
    } catch (err) {
        schShowError('schScheduleFormError', 'Помилка: ' + err.message);
    }
}

// ── Wire events ───────────────────────────────────────────────────────
document.getElementById('schCreateJobBtn').addEventListener('click', schOpenCreateJobModal);
document.getElementById('schRefreshBtn').addEventListener('click',   schLoadJobs);
document.getElementById('schRunNowBtn').addEventListener('click',    schRunNow);
document.getElementById('schToggleEnableBtn').addEventListener('click', schToggleEnable);
document.getElementById('schEditJobBtn').addEventListener('click',   schOpenEditJobModal);
document.getElementById('schEditScheduleBtn').addEventListener('click', schOpenScheduleModal);
document.getElementById('schRefreshRunsBtn').addEventListener('click', () => {
    if (schState.selectedJobId) schLoadJobRuns(schState.selectedJobId);
});

// Job modal
document.getElementById('schJobForm').addEventListener('submit', schSubmitJobForm);
document.getElementById('schJobCancel').addEventListener('click', () => {
    document.getElementById('schJobModal').close();
});

// Schedule modal
document.getElementById('schScheduleForm').addEventListener('submit', schSubmitScheduleForm);
document.getElementById('schScheduleCancel').addEventListener('click', () => {
    document.getElementById('schScheduleModal').close();
});
document.getElementById('schSchedType').addEventListener('change', e => {
    schToggleSchedFields(e.target.value);
});

// ── fetchJson needs to surface HTTP status for 409 handling ───────────
// Wrap the global fetchJson to attach status to error objects
(function patchFetchJson() {
    const _orig = window.fetchJson;
    if (!_orig) return;
    window.fetchJson = async function(url, opts) {
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            let msg;
            try {
                const j = await resp.json();
                msg = j.message || j.error || resp.statusText;
            } catch { msg = resp.statusText; }
            const err = new Error(`${resp.status}: ${msg}`);
            err.status = resp.status;
            err.responseBody = msg;
            throw err;
        }
        return resp.json();
    };
})();

// ── Expose for service.js tab switch ─────────────────────────────────
window.schLoadJobs = schLoadJobs;

} // end guard

