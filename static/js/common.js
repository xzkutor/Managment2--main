/* common.js — shared helpers for all Pricewatch pages */
'use strict';

/**
 * Fetch JSON; throws Error with message from response body on non-2xx.
 */
async function fetchJson(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        let message = 'Request failed';
        try { const d = await res.json(); message = d.error || JSON.stringify(d); }
        catch (_) { message = res.statusText; }
        throw new Error(message);
    }
    return res.json();
}

/** Escape HTML special chars. */
function escHtml(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Set text + class of a named status-pill or status-msg by element id.
 * type: 'info' | 'warning' | 'error' | 'success'
 */
function setStatusPill(elementId, message, type = 'info') {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = message;
    el.className = `status-pill status-${type}`;
}

/**
 * Show an inline status message inside a container element.
 * type: 'info' | 'warn' | 'error'
 */
function showStatusMsg(containerEl, html, type = 'info') {
    if (!containerEl) return;
    containerEl.innerHTML = html;
    containerEl.className = containerEl.className
        .replace(/\b(error|warn|success)\b/g, '').trim();
    if (type === 'error') containerEl.classList.add('error');
    else if (type === 'warn') containerEl.classList.add('warn');
}

/** Show a plain muted error paragraph inside a container element. */
function showError(containerEl, message) {
    if (!containerEl) return;
    containerEl.innerHTML =
        `<p class="muted" style="color:var(--error-text);">${escHtml(message)}</p>`;
}

