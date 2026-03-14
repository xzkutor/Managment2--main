/* service.scheduler.render.js — Scheduler DOM rendering */
'use strict';

// ── Format helpers ────────────────────────────────────────────────────

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
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    if (h) return `${h}г ${m}хв`; if (m) return `${m}хв ${s}с`; return `${s}с`;
}

function schStatusCls(st) {
    return ({ queued: 'info', running: 'warning', success: 'success', finished: 'success',
        partial: 'warning', failed: 'error', skipped: 'info', cancelled: 'info', retry: 'warning' })[st?.toLowerCase()] || 'info';
}

function schStatusLabel(st) {
    return ({ queued: '🕒 queued', running: '⚙ running', success: '✓ success', finished: '✓ finished',
        partial: '⚠ partial', failed: '✗ failed', skipped: '⊘ skipped', cancelled: '⊝ cancelled', retry: '🔄 retry' })[st?.toLowerCase()] || (st || '—');
}

function schTriggerLabel(t) {
    return ({ manual: '🖱 manual', scheduled: '⏱ scheduled', retry: '🔄 retry' })[t] || (t || '—');
}

function schInfoRow(label, value) {
    return `<div class="sch-info-row"><span class="sch-info-label">${label}</span><span class="sch-info-value">${value}</span></div>`;
}

function schShowError(elId, msg) {
    const el = document.getElementById(elId); if (!el) return;
    el.textContent = msg; el.classList.toggle('hidden', !msg);
}

function _storeName(id) {
    if (!id || !schState.refData.stores) return `#${id || '—'}`;
    const s = schState.refData.stores.find(x => x.id === id);
    return s ? escHtml(s.name) : `#${id}`;
}

function _catName(catId, storeId) {
    if (!catId) return '—';
    const c = (schState.refData.categories[storeId] || []).find(x => x.id === catId);
    return c ? escHtml(c.name) : `#${catId}`;
}

// ── Jobs list ─────────────────────────────────────────────────────────

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
                <span class="sch-badge ${eCls}">${j.enabled ? 'ON' : 'OFF'}</span>
            </div>
            <div class="sch-job-item-sub">${escHtml(spec.label)}</div>
            ${storeTxt ? `<div class="sch-job-item-store">${storeTxt}</div>` : ''}
            <div class="sch-job-item-next"><span>▶ ${next}</span><span>${hints}</span></div>
        </div>`;
    }).join('');
    container.querySelectorAll('.sch-job-item').forEach(el =>
        el.addEventListener('click', () => schSelectJob(Number(el.dataset.id))));
}

// ── Job detail panel ──────────────────────────────────────────────────

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

    const knownKeys = new Set(['store_id', 'category_id']);
    const extra = job.params_json ? Object.fromEntries(Object.entries(job.params_json).filter(([k]) => !knownKeys.has(k))) : null;
    const extraBlock = extra && Object.keys(extra).length
        ? `<details class="sch-advanced-block"><summary>▸ Додаткові params</summary><code class="sch-params-code">${escHtml(JSON.stringify(extra, null, 2))}</code></details>` : '';

    document.getElementById('schJobFields').innerHTML = rows.join('') + extraBlock;
    schRenderSchedule(schState.selectedSchedule);
    const s = document.getElementById('schRunNowStatus'); s.style.display = 'none';
}

// ── Schedule card ─────────────────────────────────────────────────────

function schRenderSchedule(sched) {
    const el = document.getElementById('schScheduleFields');
    if (!sched) {
        el.innerHTML = `<div class="sch-no-schedule"><span class="muted">Розклад не налаштовано</span></div>`;
        return;
    }
    const rows = [schInfoRow('Тип', sched.schedule_type === 'interval' ? '⏱ Інтервал' : '🗓 Cron')];
    if (sched.schedule_type === 'interval') rows.push(schInfoRow('Кожні', schFmtInterval(sched.interval_sec)));
    else if (sched.schedule_type === 'cron') {
        rows.push(schInfoRow('Cron', `<code class="sch-cron-code">${escHtml(sched.cron_expr || '—')}</code>`));
        rows.push(schInfoRow('Timezone', escHtml(sched.timezone || 'UTC')));
    }
    if (sched.jitter_sec) rows.push(schInfoRow('Jitter', schFmtInterval(sched.jitter_sec)));
    rows.push(schInfoRow('Misfire', escHtml(sched.misfire_policy || 'skip')));
    rows.push(schInfoRow('Статус', sched.enabled
        ? '<span class="sch-badge sch-badge-enabled">увімк</span>'
        : '<span class="sch-badge sch-badge-disabled">вимк</span>'));
    el.innerHTML = rows.join('');
}

// ── Recent runs table ─────────────────────────────────────────────────

function schRenderRunsTable(runs) {
    const c = document.getElementById('schRunsTable');
    if (!runs.length) { c.innerHTML = '<p class="muted sch-empty">Запусків ще не було</p>'; return; }
    const rows = runs.map(r => {
        const retryBadge = r.retryable && r.status === 'failed'
            ? '<span class="sch-badge sch-badge-retry" title="Буде повторено">↺</span>' : '';
        const errRow = r.error_message
            ? `<tr class="sch-err-row"><td colspan="6"><div class="sch-run-error" title="${escHtml(r.error_message)}">✗ ${escHtml(r.error_message.slice(0, 140))}${r.error_message.length > 140 ? '…' : ''}</div></td></tr>` : '';
        return `<tr>
            <td>${schFmtDate(r.queued_at || r.started_at)}</td>
            <td>${schTriggerLabel(r.trigger_type)}</td>
            <td><span class="sch-attempt-badge">#${r.attempt || 1}</span></td>
            <td><span class="status-pill status-${schStatusCls(r.status)}">${schStatusLabel(r.status)}</span>${retryBadge}</td>
            <td class="sch-worker-cell">${escHtml(r.worker_id || '—')}</td>
            <td><button class="btn-ghost btn-sm" data-rid="${r.id}" title="Деталі">↗</button></td>
        </tr>${errRow}`;
    }).join('');
    c.innerHTML = `<table class="sch-runs-table">
        <thead><tr><th>Старт</th><th>Тригер</th><th>Спроба</th><th>Статус</th><th>Worker</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    c.querySelectorAll('button[data-rid]').forEach(btn =>
        btn.addEventListener('click', () => showRunDetails(Number(btn.dataset.rid))));
}

