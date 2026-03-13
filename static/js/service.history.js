/* service.history.js — History tab logic */
'use strict';

// ── Data loading ──────────────────────────────────────────────────────

async function loadHistory(reset = false) {
    if (reset) serviceState.history.page = 0;
    const { page, pageSize } = serviceState.history;
    const storeId = document.getElementById('historyStoreFilter').value  || null;
    const runType = document.getElementById('historyTypeFilter').value   || null;
    const status  = document.getElementById('historyStatusFilter').value || null;
    const triggerEl = document.getElementById('historyTriggerFilter');
    const trigger = triggerEl ? triggerEl.value || null : null;

    const params = new URLSearchParams();
    if (storeId)  params.set('store_id',    storeId);
    if (runType)  params.set('run_type',    runType);
    if (status)   params.set('status',      status);
    if (trigger)  params.set('trigger_type', trigger);
    params.set('limit',  String(pageSize));
    params.set('offset', String(page * pageSize));

    setStatusPill('historyStatus', 'Завантаження…', 'warning');
    try {
        const data = await fetchJson(`/api/scrape-runs?${params.toString()}`);
        const runs = data.runs || [];
        renderHistoryTable(runs);
        setStatusPill('historyStatus', `Записів: ${runs.length}`, runs.length ? 'success' : 'info');
        document.getElementById('historyPageLabel').textContent = `Сторінка ${page + 1}`;
        document.getElementById('historyPrev').disabled = page === 0;
    } catch (err) {
        setStatusPill('historyStatus', 'Помилка: ' + err.message, 'error');
        document.getElementById('historyTable').innerHTML = '';
    }
}

// ── Rendering ─────────────────────────────────────────────────────────

function _historyStatusCls(status) {
    if (!status) return 'warning';
    const s = status.toLowerCase();
    if (s === 'success' || s === 'finished') return 'success';
    if (s === 'failed')  return 'error';
    if (s === 'running') return 'warning';
    if (s === 'queued')  return 'info';
    if (s === 'partial') return 'warning';
    return 'info';
}

function _historyTriggerLabel(trigger) {
    if (!trigger) return '—';
    return ({ manual: '🖱 manual', scheduled: '⏱ scheduled', retry: '🔄 retry' })[trigger] || trigger;
}

function renderHistoryTable(runs) {
    if (!runs.length) {
        document.getElementById('historyTable').innerHTML = '<p class="muted">Немає записів. Синхронізуйте дані.</p>';
        return;
    }
    const rows = runs.map(r => {
        const store   = r.store ? r.store.name : (r.store_id ? `#${r.store_id}` : '—');
        const date    = r.started_at
            ? new Date(r.started_at).toLocaleString()
            : (r.queued_at ? new Date(r.queued_at).toLocaleString() : '—');
        const sCls    = _historyStatusCls(r.status);
        const trigger = _historyTriggerLabel(r.trigger_type);
        const attempt = r.attempt > 1 ? ` <span class="sch-attempt-badge">×${r.attempt}</span>` : '';
        return `<tr>
            <td>${date}</td>
            <td>${escHtml(store)}</td>
            <td>${escHtml(r.run_type || '—')}</td>
            <td>${trigger}</td>
            <td><span class="status-pill status-${sCls}">${escHtml(r.status || '—')}</span>${attempt}</td>
            <td><button class="ghost" data-id="${r.id}" data-action="details">Деталі</button></td>
        </tr>`;
    }).join('');
    document.getElementById('historyTable').innerHTML = `
        <table>
            <thead><tr><th>Дата</th><th>Магазин</th><th>Тип</th><th>Тригер</th><th>Статус</th><th>Дії</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
    document.getElementById('historyTable').querySelectorAll('button[data-action]').forEach(btn =>
        btn.addEventListener('click', () => handleHistoryAction(btn.dataset.action, Number(btn.dataset.id))));
}

function handleHistoryAction(action, runId) {
    if (action === 'details') showRunDetails(runId);
}

// ── Run details modal ─────────────────────────────────────────────────

async function showRunDetails(runId) {
    const dialog = document.getElementById('runDetailsModal');
    document.getElementById('runDetails').textContent = 'Завантаження…';
    dialog.showModal();
    try {
        const data = await fetchJson(`/api/scrape-runs/${runId}`);
        document.getElementById('runDetails').textContent = JSON.stringify(data.run || data, null, 2);
    } catch (err) {
        document.getElementById('runDetails').textContent = 'Помилка: ' + err.message;
    }
}

// ── Event wiring ──────────────────────────────────────────────────────

(function historyWireEvents() {
    const prevBtn  = document.getElementById('historyPrev');
    const nextBtn  = document.getElementById('historyNext');
    const closeBtn = document.getElementById('runDetailsClose');

    if (prevBtn) prevBtn.addEventListener('click', () => {
        if (serviceState.history.page > 0) { serviceState.history.page--; loadHistory(); }
    });
    if (nextBtn) nextBtn.addEventListener('click', () => {
        serviceState.history.page++;
        loadHistory();
    });
    if (closeBtn) closeBtn.addEventListener('click', () => {
        const d = document.getElementById('runDetailsModal');
        if (d.open) d.close();
    });
})();

