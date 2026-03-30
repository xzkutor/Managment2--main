/**
 * MappingsTable.test.ts — Commit 03 regression: Тип and Confidence columns removed.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MappingsTable from '@/pages/service/mappings/components/MappingsTable.vue'
import type { MappingRow } from '@/types/mappings'

const mappings: MappingRow[] = [
  {
    id: 1,
    reference_category_id: 10,
    target_category_id: 20,
    reference_category_name: 'Ковзани',
    target_category_name: 'Skates',
    reference_store_id: 1,
    target_store_id: 2,
    match_type: 'exact',
    confidence: 0.98,
    updated_at: null,
  },
]

const EMPTY_SET = new Set<number>()

describe('MappingsTable — simplified columns (Commit 03)', () => {
  it('renders reference category column', () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    expect(w.text()).toContain('Ковзани')
  })

  it('renders target category column', () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    expect(w.text()).toContain('Skates')
  })

  it('does NOT render Тип column header', () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    const headers = w.findAll('th').map((h) => h.text())
    expect(headers).not.toContain('Тип')
  })

  it('does NOT render Confidence column header', () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    const headers = w.findAll('th').map((h) => h.text())
    expect(headers).not.toContain('Confidence')
  })

  it('does NOT render match_type cell value', () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    expect(w.text()).not.toContain('exact')
  })

  it('does NOT render confidence cell value', () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    expect(w.text()).not.toContain('98%')
  })

  it('has exactly 3 columns: ref-cat, target-cat, actions', () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    expect(w.findAll('th')).toHaveLength(3)
  })

  it('renders Edit and Delete buttons', () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    expect(w.text()).toContain('Редагувати')
    expect(w.text()).toContain('Видалити')
  })

  it('emits edit event on edit click', async () => {
    const w = mount(MappingsTable, { props: { mappings, deletingIds: EMPTY_SET } })
    await w.findAll('button').find((b) => b.text() === 'Редагувати')!.trigger('click')
    expect(w.emitted('edit')).toBeTruthy()
    expect(w.emitted('edit')![0]).toEqual([mappings[0]])
  })
})
