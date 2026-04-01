<template>
  <aside class="cw-rail panel">

    <!-- ── Target store selector ─────────────────────────── -->
    <div>
      <label for="cw-target-store" class="cw-rail-label">Цільовий магазин</label>
      <select id="cw-target-store" :value="targetStoreId ?? ''" @change="onTargetStoreChange">
        <option value="">Всі цільові магазини</option>
        <option v-for="s in targetStores" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </div>

    <div class="cw-rail-divider" />

    <!-- ── Reference category list ──────────────────────── -->
    <div class="cw-rail-categories" style="flex:1;min-height:0;">
      <span class="cw-rail-label">Референсна категорія</span>

      <div v-if="loadingCategories" class="muted" style="font-size:0.88rem;">Завантаження…</div>

      <div v-else-if="!categories.length" class="muted" style="font-size:0.88rem;">
        Немає категорій. Синхронізуйте на сервісній сторінці.
      </div>

      <div v-else class="select-list">
        <div
          v-for="cat in categories"
          :key="cat.id"
          class="select-list-item cw-cat-row"
          :class="{ active: activeCategoryId === cat.id }"
          role="button"
          tabindex="0"
          @click="emit('select-category', cat.id)"
          @keydown.enter="emit('select-category', cat.id)"
          @keydown.space.prevent="emit('select-category', cat.id)"
        >
          <span class="cw-cat-name">{{ cat.name }}</span>
          <span
            v-if="cat.product_count != null"
            :class="['badge', 'badge-cat', 'cw-cat-count', cat.product_count === 0 ? 'cw-cat-count--empty' : '']"
            :title="cat.product_count === 0 ? 'Немає товарів у категорії' : `${cat.product_count} товарів`"
          >{{ cat.product_count }}</span>
        </div>
      </div>
    </div>

    <div class="cw-rail-divider" />

    <!-- ── Compare action ───────────────────────────────── -->
    <div>
      <button
        class="btn"
        style="width:100%;"
        :disabled="!canCompare || comparing"
        @click="emit('compare')"
      >
        <span v-if="comparing"><span class="spinner" />Виконується…</span>
        <span v-else>▶ Порівняти</span>
      </button>
      <div v-if="statusText && !comparing" class="muted" style="font-size:0.8rem;margin-top:8px;line-height:1.4;">
        {{ statusText }}
      </div>
    </div>

  </aside>
</template>

<script setup lang="ts">
/**
 * ComparisonControlRail.vue — Left sticky control rail for the comparison workspace.
 *
 * Contains (RFC-016):
 *   - target store selector  (operator-selectable)
 *   - reference category list (operator selects one)
 *   - compare action button + status text
 *
 * Does NOT contain:
 *   - reference store selector (backend-defined, auto-selected)
 *   - mapped-target-category checkboxes (auto-derived from mappings)
 */
import type { StoreSummary, CategorySummary } from '@/types/store'

interface Props {
  targetStores:      StoreSummary[]
  targetStoreId:     number | null
  categories:        CategorySummary[]
  loadingCategories: boolean
  activeCategoryId:  number | null
  canCompare:        boolean
  comparing:         boolean
  statusText:        string
}
withDefaults(defineProps<Props>(), {
  targetStores:      () => [],
  targetStoreId:     null,
  categories:        () => [],
  loadingCategories: false,
  activeCategoryId:  null,
  canCompare:        false,
  comparing:         false,
  statusText:        '',
})

const emit = defineEmits<{
  (e: 'update:target-store',  id: number | null): void
  (e: 'select-category',      id: number):        void
  (e: 'compare'):                                  void
}>()

function onTargetStoreChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  emit('update:target-store', val ? Number(val) : null)
}
</script>

