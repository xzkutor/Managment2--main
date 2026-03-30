/**
 * useServiceSections.ts — section descriptor composable for the Service Console.
 *
 * Replaces the tab-based useServiceTabs.ts with a route-addressable model.
 * Each service section maps to a named child route under /service.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ServiceSectionDef {
  id: string
  label: string
  /** Emoji icon displayed in the section rail. */
  icon: string
  /** Vue Router named route for this section. */
  routeName: string
}

// ---------------------------------------------------------------------------
// Section registry
// ---------------------------------------------------------------------------

export const SERVICE_SECTIONS: ServiceSectionDef[] = [
  {
    id: 'categories',
    label: 'Категорії',
    icon: '📁',
    routeName: 'service-categories',
  },
  {
    id: 'mappings',
    label: 'Мапінги',
    icon: '🔗',
    routeName: 'service-mappings',
  },
  {
    id: 'scheduler',
    label: 'Планувальник',
    icon: '⏱',
    routeName: 'service-scheduler',
  },
  {
    id: 'history',
    label: 'Історія',
    icon: '📋',
    routeName: 'service-history',
  },
]

