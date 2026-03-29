/**
 * navigation.ts — canonical SPA navigation link definitions.
 *
 * Single source of truth for all operator-facing route destinations.
 * Consumed by AppShellSidebarNav (and any future nav component).
 * Do NOT duplicate this list in individual components.
 */

export interface NavLink {
  /** Vue Router path */
  to: string
  /** Display label */
  label: string
}

export const NAV_LINKS: ReadonlyArray<NavLink> = [
  { to: '/',        label: '🏠 Порівняння' },
  { to: '/service', label: '🔧 Service Console' },
  { to: '/gap',     label: '📋 Розрив асортименту' },
  { to: '/matches', label: '✅ Підтверджені збіги' },
] as const

