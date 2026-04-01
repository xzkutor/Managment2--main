<template>
  <div class="gap-group-panel">

    <!-- Group header: category name + item count -->
    <div class="gap-group-header">
      <h3 class="gap-group-title">{{ group.target_category?.name ?? '—' }}</h3>
      <span class="badge badge-cat gap-group-count">
        {{ group.count }} {{ group.count === 1 ? 'товар' : 'товарів' }}
      </span>
    </div>

    <!-- Result rows -->
    <div class="gap-group-body">
      <div
        v-for="item in group.items"
        :key="item.target_product?.id ?? String(Math.random())"
        class="gap-row"
        :class="{ 'gap-row--in-progress': actionInProgressId === item.target_product?.id }"
      >

        <!-- Product info -->
        <div class="gap-row-info">
          <a
            v-if="item.target_product?.product_url"
            class="gap-row-name link-btn"
            :href="item.target_product.product_url"
            target="_blank"
            rel="noopener"
          >{{ item.target_product?.name ?? '—' }}</a>
          <span v-else class="gap-row-name">{{ item.target_product?.name ?? '—' }}</span>

          <div class="gap-row-meta">
            <span class="gap-row-price">{{ formatPrice(item.target_product) }}</span>
            <span v-if="item.target_product?.is_available" class="gap-avail gap-avail--yes">✓ є</span>
            <span v-else class="gap-avail gap-avail--no">✗ нема</span>
            <span :class="['badge', `badge-${item.status}`, 'gap-status-badge']">
              {{ statusLabel(item.status) }}
            </span>
          </div>
        </div>

        <!-- Action area -->
        <div class="gap-row-actions">
          <!-- Spinner shown when THIS row's action is in flight -->
          <span
            v-if="actionInProgressId === item.target_product?.id"
            class="gap-row-action-pending"
          >
            <span class="spinner" aria-hidden="true"></span>
          </span>

          <!-- Buttons: always rendered; disabled when any action is in progress -->
          <button
            v-if="item.status === 'new'"
            class="btn btn-sm gap-btn-take"
            type="button"
            :disabled="actionInProgressId !== null"
            :title="'Взяти в роботу: ' + (item.target_product?.name ?? '')"
            :aria-label="'Взяти в роботу: ' + (item.target_product?.name ?? '')"
            @click="item.target_product && emit('action', refCategoryId, item.target_product.id, 'in_progress')"
          >
            Взяти в роботу
          </button>
          <button
            v-else-if="item.status === 'in_progress'"
            class="btn btn-sm gap-btn-done"
            type="button"
            :disabled="actionInProgressId !== null"
            :title="'Позначити опрацьованим: ' + (item.target_product?.name ?? '')"
            :aria-label="'Позначити опрацьованим: ' + (item.target_product?.name ?? '')"
            @click="item.target_product && emit('action', refCategoryId, item.target_product.id, 'done')"
          >
            Позначити опрацьованим
          </button>
          <span v-else class="gap-done-mark" title="Опрацьовано">✓</span>
        </div>

      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
/**
 * GapGroupTable.vue — workspace result panel for one mapped target category (Commits 6, 8).
 *
 * Each group renders as a self-contained panel with a clear heading, compact rows,
 * and polished action buttons with in-progress state.
 * Emits 'action' with (refCatId, targetProductId, newStatus) on row button click.
 */
import type { GapGroup, GapItemStatus, GapProduct } from '@/types/gap'

interface Props {
  group: GapGroup
  refCategoryId: number
  actionInProgressId: number | null
}

withDefaults(defineProps<Props>(), { actionInProgressId: null })

const emit = defineEmits<{
  (e: 'action', refCatId: number, targetProductId: number, status: GapItemStatus): void
}>()

function formatPrice(p: GapProduct | null | undefined): string {
  if (!p) return '—'
  const v = p.price
  if (v == null || v === '') return '—'
  const num = typeof v === 'string' ? parseFloat(v) : v
  if (isNaN(num)) return String(v)
  return p.currency ? `${num.toFixed(2)} ${p.currency}` : num.toFixed(2)
}

function statusLabel(status: GapItemStatus): string {
  return ({ new: 'Новий', in_progress: 'В роботі', done: 'Опрацьовано' } as Record<string, string>)[status] ?? status
}
</script>

<style scoped>
.gap-group-panel {
  background: var(--panel);
  border-radius: var(--radius-xl);
  box-shadow: 0 4px 16px rgba(82,86,133,0.07);
  overflow: hidden;
  margin-bottom: 16px;
}

.gap-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px 10px;
  border-bottom: 1px solid var(--border);
  background: #f8f9ff;
}
.gap-group-title {
  font-size: 0.98rem;
  font-weight: 700;
  margin: 0;
  flex: 1;
  min-width: 0;
}
.gap-group-count {
  flex-shrink: 0;
  font-size: 0.75rem;
}

.gap-group-body {
  padding: 4px 0;
}

.gap-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  border-bottom: 1px solid #f0f1f8;
  transition: background 0.1s;
}
.gap-row:last-child { border-bottom: none; }
.gap-row:hover { background: #fafaff; }
.gap-row--in-progress { opacity: 0.65; }

.gap-row-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.gap-row-name {
  font-weight: 500;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gap-row-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.gap-row-price {
  font-size: 0.82rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.gap-avail {
  font-size: 0.78rem;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
}
.gap-avail--yes { background: #d1fae5; color: #065f46; }
.gap-avail--no  { background: #fee2e2; color: #991b1b; }
.gap-status-badge { font-size: 0.72rem; }

.gap-row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.gap-btn-take {
  background: var(--info-bg, #eff6ff);
  color: var(--info-text, #1e40af);
  border: 1px solid #bfdbfe;
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.13s;
  white-space: nowrap;
}
.gap-btn-take:hover { background: #dbeafe; }
.gap-btn-done {
  background: var(--success-bg, #d1fae5);
  color: var(--success-text, #065f46);
  border: 1px solid #6ee7b7;
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.13s;
  white-space: nowrap;
}
.gap-btn-done:hover { background: #a7f3d0; }
.gap-done-mark {
  color: #059669;
  font-weight: 700;
  font-size: 1rem;
}
.gap-row-action-pending {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
}
</style>
