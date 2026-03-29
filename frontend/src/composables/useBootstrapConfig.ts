/**
 * useBootstrapConfig — reads the normalized PricewatchBootstrap config from
 * the browser window.
 *
 * Resolution order:
 *   1. window.__PRICEWATCH_BOOTSTRAP__  (canonical, injected by all page shells)
 *   2. window.SERVICE_CONFIG            (deprecated legacy alias for service.html;
 *                                        kept for backward compat during migration)
 *   3. built-in defaults
 *
 * This is a plain function, not a Vue composable — it has no lifecycle hooks
 * and is safe to call from computed getters, store factories, or onMounted.
 */
import type { PricewatchBootstrap } from '@/types/bootstrap'

const DEFAULTS: PricewatchBootstrap = {
  enableAdminSync: false,
}

export function useBootstrapConfig(): PricewatchBootstrap {
  // 1. Canonical normalized bootstrap
  const bootstrap = window.__PRICEWATCH_BOOTSTRAP__
  if (bootstrap !== undefined) {
    return {
      enableAdminSync: bootstrap.enableAdminSync ?? DEFAULTS.enableAdminSync,
    }
  }

  // 2. Legacy SERVICE_CONFIG fallback (service.html prior to bootstrap migration)
  const legacy = window.SERVICE_CONFIG
  if (legacy !== undefined) {
    return {
      enableAdminSync: legacy.enableAdminSync ?? DEFAULTS.enableAdminSync,
    }
  }

  // 3. Safe defaults
  return { ...DEFAULTS }
}

