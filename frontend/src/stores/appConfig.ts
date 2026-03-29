/**
 * appConfig store — bootstrap / runtime config for the SPA.
 *
 * Minimal store intended to hold values injected at app boot time
 * (e.g. via a JSON payload on the SPA shell or a /api/app-config endpoint).
 *
 * Do NOT use this store for page-local component state.
 * Page-local ephemeral state should live inside route composables/components.
 *
 * Shape will grow in later commits once the Flask SPA shell is in place
 * and a bootstrap delivery strategy is confirmed.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useBootstrapConfig } from '@/composables/useBootstrapConfig'

export const useAppConfigStore = defineStore('appConfig', () => {
  // Read normalized bootstrap once at store creation time.
  // Static config values do not change after page load.
  const _bootstrap = useBootstrapConfig()

  /**
   * Whether admin store-sync actions are enabled.
   * Sourced from window.__PRICEWATCH_BOOTSTRAP__.enableAdminSync.
   */
  const enableAdminSync = ref<boolean>(_bootstrap.enableAdminSync)

  /** App version string, injected from the SPA shell if available. */
  const version = ref<string | null>(null)

  /** Arbitrary key/value runtime flags delivered at boot time. */
  const flags = ref<Record<string, unknown>>({})

  function setConfig(config: { version?: string; flags?: Record<string, unknown> }) {
    if (config.version !== undefined) version.value = config.version
    if (config.flags !== undefined) flags.value = config.flags
  }

  return { enableAdminSync, version, flags, setConfig }
})

