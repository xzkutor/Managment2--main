/**
 * MappingDrawerDefaults.test.ts — Commit 09 assertions for MappingDrawer.vue.
 *
 * Key assertions:
 *  1. Drawer form does NOT show match_type or confidence fields.
 *  2. Drawer form shows only: reference category, target store, target category.
 *  3. In create mode the target store defaults to defaultTargetStoreId (from service context).
 *  4. Changing target store triggers category reload.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import MappingDrawer from '@/pages/service/mappings/components/MappingDrawer.vue'

// ---------------------------------------------------------------------------
// Stubs & mocks
// ---------------------------------------------------------------------------

/** Stub DrawerShell to render its body/footer slots inline (avoids Teleport). */
vi.mock('@/components/base/DrawerShell.vue', () => ({
  default: {
    template: `
      <div class="drawer-shell-stub" :data-open="open" :data-title="title">
        <slot />
        <div class="drawer-footer-stub"><slot name="footer" /></div>
      </div>
    `,
    props: ['open', 'title'],
    emits: ['close'],
  },
}))

vi.mock('@/api/client', () => ({
  fetchCategoriesForStore: vi.fn(),
}))

import * as client from '@/api/client'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const refCategories = [
  { id: 10, store_id: 1, name: 'Ковзани', normalized_name: 'kovzany', url: null, external_id: null, updated_at: null },
  { id: 11, store_id: 1, name: 'Шоломи', normalized_name: 'sholomy', url: null, external_id: null, updated_at: null },
]
const targetStores = [
  { id: 2, name: 'hockeyworld', is_reference: false, base_url: null },
  { id: 3, name: 'pricetest',   is_reference: false, base_url: null },
]
const targetCats2 = [
  { id: 20, store_id: 2, name: 'Skates', normalized_name: 'kovzany', url: null, external_id: null, updated_at: null },
]
const editMapping = {
  id: 1,
  reference_category_id: 10,
  target_category_id: 20,
  reference_category_name: 'Ковзани',
  target_category_name: 'Skates',
  reference_store_id: 1,
  target_store_id: 2,
  match_type: 'exact',
  confidence: 1.0,
  updated_at: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(client.fetchCategoriesForStore).mockResolvedValue(targetCats2)
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mountDrawer(props: Record<string, unknown>) {
  return mount(MappingDrawer, {
    props: {
      open: true,
      mode: 'create',
      refCategories,
      targetStores,
      defaultTargetStoreId: null,
      defaultTargetCategories: [],
      ...props,
    },
  })
}

// ---------------------------------------------------------------------------
// 1. Form field presence / absence
// ---------------------------------------------------------------------------

describe('MappingDrawer — simplified form fields (Commit 05)', () => {
  it('renders reference category selector', () => {
    const w = mountDrawer({})
    expect(w.find('#mdr-ref-cat').exists()).toBe(true)
  })

  it('renders target store selector', () => {
    const w = mountDrawer({})
    expect(w.find('#mdr-tgt-store').exists()).toBe(true)
  })

  it('renders target category selector', () => {
    const w = mountDrawer({})
    expect(w.find('#mdr-tgt-cat').exists()).toBe(true)
  })

  it('does NOT render match_type input', () => {
    const w = mountDrawer({})
    // match_type was removed in Commit 05
    expect(w.find('input[placeholder*="manual"]').exists()).toBe(false)
    expect(w.find('#md-match-type').exists()).toBe(false)
  })

  it('does NOT render confidence input', () => {
    const w = mountDrawer({})
    // confidence was removed in Commit 05
    expect(w.find('#md-confidence').exists()).toBe(false)
    expect(w.find('input[placeholder*="0.95"]').exists()).toBe(false)
  })

  it('has exactly 3 selects (ref-cat, tgt-store, tgt-cat)', () => {
    const w = mountDrawer({})
    expect(w.findAll('select')).toHaveLength(3)
  })
})

// ---------------------------------------------------------------------------
// 2. Target store defaults from service context (Commit 03 + 05)
// ---------------------------------------------------------------------------

describe('MappingDrawer — target store defaults from service context', () => {
  it('defaults target store select to defaultTargetStoreId on create', () => {
    // The form is initialised with emptyForm() which reads defaultTargetStoreId
    const w = mountDrawer({ defaultTargetStoreId: 2 })
    const select = w.find('#mdr-tgt-store').element as HTMLSelectElement
    expect(select.value).toBe('2')
  })

  it('target store select is empty when defaultTargetStoreId is null', () => {
    const w = mountDrawer({ defaultTargetStoreId: null })
    const select = w.find('#mdr-tgt-store').element as HTMLSelectElement
    expect(select.value).toBe('')
  })

  it('pre-populates target categories when defaultTargetCategories provided', () => {
    const w = mountDrawer({
      defaultTargetStoreId:   2,
      defaultTargetCategories: targetCats2,
    })
    // The target category select should list the default categories
    const opts = w.find('#mdr-tgt-cat').findAll('option')
    expect(opts.some((o) => o.text().includes('Skates'))).toBe(true)
  })

  it('resets form when drawer opens in create mode', async () => {
    const w = mountDrawer({ defaultTargetStoreId: 2, open: false })
    await w.setProps({ open: true })
    const select = w.find('#mdr-tgt-store').element as HTMLSelectElement
    expect(select.value).toBe('2')
  })
})

// ---------------------------------------------------------------------------
// 3. Edit mode — category pair locked; form pre-filled from mapping
// ---------------------------------------------------------------------------

describe('MappingDrawer — edit mode', () => {
  it('pre-fills reference category from the mapping', async () => {
    const w = mountDrawer({ mode: 'edit', mapping: editMapping, open: false })
    await w.setProps({ open: true })
    await new Promise((r) => setTimeout(r, 0)) // let watch settle
    const refSelect = w.find('#mdr-ref-cat').element as HTMLSelectElement
    expect(refSelect.value).toBe('10')
  })

  it('pre-fills target store from the mapping', async () => {
    const w = mountDrawer({ mode: 'edit', mapping: editMapping, open: false })
    await w.setProps({ open: true })
    await new Promise((r) => setTimeout(r, 0))
    const tgtStore = w.find('#mdr-tgt-store').element as HTMLSelectElement
    expect(tgtStore.value).toBe('2')
  })

  it('target store select is disabled in edit mode', () => {
    const w = mountDrawer({ mode: 'edit', mapping: editMapping })
    const select = w.find('#mdr-tgt-store').element as HTMLSelectElement
    expect(select.disabled).toBe(true)
  })

  it('reference category select is disabled in edit mode', () => {
    const w = mountDrawer({ mode: 'edit', mapping: editMapping })
    const refSelect = w.find('#mdr-ref-cat').element as HTMLSelectElement
    expect(refSelect.disabled).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 4. Changing target store loads categories via API
// ---------------------------------------------------------------------------

describe('MappingDrawer — target store change loads categories', () => {
  it('fetches categories when target store is changed', async () => {
    vi.mocked(client.fetchCategoriesForStore).mockResolvedValue(targetCats2)

    const w = mountDrawer({ defaultTargetStoreId: null })
    const select = w.find('#mdr-tgt-store')
    await select.setValue('2')
    await new Promise((r) => setTimeout(r, 0)) // let async load settle

    expect(client.fetchCategoriesForStore).toHaveBeenCalledWith(2)
  })

  it('clears target category when target store changes', async () => {
    const w = mountDrawer({ defaultTargetStoreId: 2, defaultTargetCategories: targetCats2 })
    const tgtStore = w.find('#mdr-tgt-store')
    // Change to a different store
    await tgtStore.setValue('3')
    const tgtCat = w.find('#mdr-tgt-cat').element as HTMLSelectElement
    expect(tgtCat.value).toBe('')
  })
})

