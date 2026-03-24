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

/**
 * Format a numeric price value with exactly 2 decimal digits.
 *
 * Examples:
 *   formatPrice(12)           → "12.00"
 *   formatPrice(12.3)         → "12.30"
 *   formatPrice(12.345)       → "12.35"
 *   formatPrice(0)            → "0.00"
 *   formatPrice(null)         → "—"
 *   formatPrice(12.3, 'UAH')  → "12.30 UAH"
 *
 * Does NOT use locale-dependent formatting; uses Number + .toFixed(2).
 *
 * @param {*}      value    Numeric price (or null/undefined for missing).
 * @param {string} currency Optional currency string appended with a space.
 * @returns {string}
 */
function formatPrice(value, currency = '') {
    if (value == null || value === '') return '—';
    const num = Number(value);
    if (!Number.isFinite(num)) return '—';
    const base = num.toFixed(2);
    return currency ? `${base} ${currency}` : base;
}

/**
 * Convenience wrapper: format price from a product object.
 * Returns "—" if product is falsy or price is missing.
 *
 * @param {{price?: *, currency?: string}|null|undefined} product
 * @returns {string}
 */
function formatProductPrice(product) {
    if (!product) return '—';
    return formatPrice(product.price, product.currency || '');
}

