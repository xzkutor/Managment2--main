/**
 * PricewatchBootstrap — normalized runtime config delivered to the browser.
 *
 * Flask injects this as `window.__PRICEWATCH_BOOTSTRAP__` in every page shell
 * (and in the future SPA shell). All fields are explicitly typed with safe
 * defaults so client code never needs to guard against undefined shapes.
 *
 * Keep this object small. It is for runtime config only — not API data.
 */
export interface PricewatchBootstrap {
  /**
   * Whether admin store-sync actions are visible in the Service Console.
   * Controlled by the ENABLE_ADMIN_SYNC Flask config / env var.
   */
  enableAdminSync: boolean
}

// ---------------------------------------------------------------------------
// Global window augmentation
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    /** Normalized bootstrap payload injected by Flask page shells. */
    __PRICEWATCH_BOOTSTRAP__?: Partial<PricewatchBootstrap>

    /**
     * @deprecated
     * Legacy per-page config global injected by service.html prior to the
     * normalized bootstrap migration. Kept as a backward-compat alias that
     * points to `window.__PRICEWATCH_BOOTSTRAP__` during the transition.
     * Will be removed when the SPA shell replaces all page-specific shells.
     */
    SERVICE_CONFIG?: { enableAdminSync?: boolean }
  }
}

