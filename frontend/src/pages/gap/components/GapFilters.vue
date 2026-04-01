<template>
  <div class="gap-filters-rail">

    <!-- ── Section: Вибір цілі ──────────────────── -->
    <div class="gap-filter-section">
      <div class="gap-filter-section-title">🎯 Ціль</div>

      <div class="form-group">
        <label for="targetStoreSelect">Цільовий магазин</label>
        <select id="targetStoreSelect" :value="selectedTargetStoreId ?? ''" @change="onTargetStoreChange">
          <option value="">— оберіть магазин —</option>
          <option v-for="s in targetStores" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>
    </div>

    <div class="gap-filter-divider" />

    <!-- ── Section: Категорія ────────────────────── -->
    <div class="gap-filter-section">
      <div class="gap-filter-section-title">📂 Категорія</div>

      <div class="form-group">
        <label for="refCategorySelect">Референсна</label>
        <select
          id="refCategorySelect"
          :value="selectedRefCategoryId ?? ''"
          :disabled="!selectedTargetStoreId || refCategoriesLoading"
          @change="onRefCategoryChange"
        >
          <option v-if="!selectedTargetStoreId" value="">— спочатку магазин —</option>
          <option v-else-if="refCategoriesLoading" value="">— завантаження… —</option>
          <option v-else value="">— оберіть категорію —</option>
          <option v-for="c in referenceCategories" :key="c.id" :value="c.id">
            {{ c.name }}{{ c.product_count ? ` (${c.product_count})` : '' }}
          </option>
        </select>
      </div>

      <div class="form-group">
        <label>Цільові (з маппінгів)</label>
        <div class="gap-mapped-cats">
          <span v-if="mappedCatsLoading" class="muted" style="font-size:0.85rem;">Завантаження…</span>
          <span v-else-if="!selectedRefCategoryId" class="muted" style="font-size:0.85rem;">Оберіть референсну</span>
          <span v-else-if="noMappingsWarning" class="muted" style="font-size:0.85rem;">
            Немає маппінгів —
            <a href="/service">налаштувати</a>
          </span>
          <label
            v-for="cat in mappedTargetCats"
            :key="cat.target_category_id"
            class="checkbox-row gap-mapped-cat-row"
          >
            <input
              type="checkbox"
              :value="cat.target_category_id"
              :checked="selectedTargetCatIds.has(cat.target_category_id)"
              @change="emit('toggle-target-cat', cat.target_category_id, ($event.target as HTMLInputElement).checked)"
            />
            <span>{{ cat.target_category_name }}</span>
          </label>
        </div>
      </div>
    </div>

    <div class="gap-filter-divider" />

    <!-- ── Section: Пошук і фільтри ─────────────── -->
    <div class="gap-filter-section">
      <div class="gap-filter-section-title">🔍 Пошук і фільтри</div>

      <div class="form-group">
        <label for="searchInput">Назва товару</label>
        <input
          id="searchInput"
          type="text"
          :value="search"
          placeholder="напр. Bauer Vapor…"
          @input="emit('update:search', ($event.target as HTMLInputElement).value)"
          @keydown.enter="emit('load')"
        />
      </div>

      <div class="form-group">
        <label class="checkbox-row">
          <input
            type="checkbox"
            :checked="onlyAvailable"
            @change="emit('update:only-available', ($event.target as HTMLInputElement).checked)"
          />
          Лише в наявності
        </label>
      </div>

      <div class="form-group">
        <label>Статуси</label>
        <div style="display:flex;flex-direction:column;gap:4px;margin-top:4px;">
          <label class="checkbox-row">
            <input type="checkbox" :checked="statuses.new"
              @change="emit('update:status-new', ($event.target as HTMLInputElement).checked)" />
            Нові
          </label>
          <label class="checkbox-row">
            <input type="checkbox" :checked="statuses.in_progress"
              @change="emit('update:status-in-progress', ($event.target as HTMLInputElement).checked)" />
            В роботі
          </label>
          <label class="checkbox-row">
            <input type="checkbox" :checked="statuses.done"
              @change="emit('update:status-done', ($event.target as HTMLInputElement).checked)" />
            Опрацьовано
          </label>
        </div>
      </div>
    </div>

    <div class="gap-filter-divider" />

    <!-- ── Section: Дія ─────────────────────────── -->
    <div class="gap-filter-section">
      <button
        class="btn"
        type="button"
        style="width:100%;"
        :disabled="!canLoad || loading"
        @click="emit('load')"
      >
        <span v-if="loading"><span class="spinner" />Завантаження…</span>
        <span v-else>Показати розрив</span>
      </button>
    </div>

  </div>
</template>

<script setup lang="ts">
/**
 * GapFilters.vue — structured left control rail for /gap (Commit 7).
 *
 * Organized into four visual sections:
 *   1. Ціль       — target store
 *   2. Категорія  — reference category + mapped target categories
 *   3. Фільтри    — search, availability, status checkboxes
 *   4. Дія        — primary load button
 *
 * All state is owned by the parent; this component only emits.
 */
import type { StoreSummary, CategorySummary } from '@/types/store'
import type { MappedTargetCategory } from '@/types/gap'
import type { GapStatusFilters } from '../composables/useGapFilters'

interface Props {
  targetStores: StoreSummary[]
  referenceCategories: CategorySummary[]
  mappedTargetCats: MappedTargetCategory[]
  selectedTargetStoreId: number | null
  selectedRefCategoryId: number | null
  selectedTargetCatIds: Set<number>
  search: string
  onlyAvailable: boolean
  statuses: GapStatusFilters
  refCategoriesLoading: boolean
  mappedCatsLoading: boolean
  noMappingsWarning: boolean
  canLoad: boolean
  loading: boolean
}

withDefaults(defineProps<Props>(), {
  targetStores: () => [],
  referenceCategories: () => [],
  mappedTargetCats: () => [],
  selectedTargetStoreId: null,
  selectedRefCategoryId: null,
  loading: false,
  refCategoriesLoading: false,
  mappedCatsLoading: false,
  noMappingsWarning: false,
  canLoad: false,
})

const emit = defineEmits<{
  (e: 'update:target-store', id: number | null): void
  (e: 'update:ref-category', id: number | null): void
  (e: 'toggle-target-cat', id: number, checked: boolean): void
  (e: 'update:search', v: string): void
  (e: 'update:only-available', v: boolean): void
  (e: 'update:status-new', v: boolean): void
  (e: 'update:status-in-progress', v: boolean): void
  (e: 'update:status-done', v: boolean): void
  (e: 'load'): void
}>()

function onTargetStoreChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  emit('update:target-store', val ? Number(val) : null)
}

function onRefCategoryChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  emit('update:ref-category', val ? Number(val) : null)
}
</script>

<style scoped>
.gap-filters-rail {
  display: flex;
  flex-direction: column;
}
.gap-filter-section {
  padding: 14px 4px 6px;
}
.gap-filter-section-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 10px;
}
.gap-filter-divider {
  height: 1px;
  background: var(--border);
  margin: 2px 0;
}
.gap-mapped-cats {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 6px;
}
.gap-mapped-cat-row {
  font-size: 0.88rem;
  padding: 2px 0;
}
</style>
