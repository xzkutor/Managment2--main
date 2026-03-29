<template>
  <tr class="mw-row">
    <!-- Reference product + category label -->
    <td>
      <a
        v-if="row.reference_product?.product_url"
        class="link-btn"
        :href="row.reference_product.product_url"
        target="_blank"
        rel="noopener"
      >{{ row.reference_product?.name || '—' }}</a>
      <span v-else>{{ row.reference_product?.name || '—' }}</span>
      <div v-if="row.reference_category" class="cat-label">
        {{ row.reference_category.name }}
      </div>
    </td>

    <!-- Reference price -->
    <td class="price-cell">{{ formatPrice(row.reference_product) }}</td>

    <!-- Target product + category label -->
    <td>
      <a
        v-if="row.target_product?.product_url"
        class="link-btn"
        :href="row.target_product.product_url"
        target="_blank"
        rel="noopener"
      >{{ row.target_product?.name || '—' }}</a>
      <span v-else>{{ row.target_product?.name || '—' }}</span>
      <div v-if="row.target_category" class="cat-label">
        {{ row.target_category.name }}
      </div>
    </td>

    <!-- Target price -->
    <td class="price-cell">{{ formatPrice(row.target_product) }}</td>

    <!-- Status badge -->
    <td>
      <span :class="['status-badge', row.match_status ?? '']">
        {{ statusLabel(row.match_status) }}
      </span>
    </td>

    <!-- Score pill -->
    <td class="score-cell">
      <span v-if="row.confidence != null" :class="['score-pill', scoreClass(row.confidence)]">
        {{ Math.round(row.confidence * 100) }}%
      </span>
      <span v-else class="muted">—</span>
    </td>

    <!-- Updated at -->
    <td class="date-cell">{{ fmtDate(row.updated_at) }}</td>

    <!-- Delete action -->
    <td class="action-cell">
      <button
        class="btn btn-sm btn-reject"
        type="button"
        :disabled="isDeletingId === row.id"
        :title="`Видалити маппінг #${row.id}`"
        @click="emit('delete', row.id)"
      >
        {{ isDeletingId === row.id ? '…' : 'Видалити' }}
      </button>
    </td>
  </tr>
</template>

<script setup lang="ts">
/**
 * MatchesTableRow.vue — single row in the /matches workspace table.
 *
 * Keeps all display logic (price formatting, score pill, status badge,
 * date formatting) local. Emits 'delete' with the mapping id upward.
 */
import type { ProductMappingRow, ProductSummary, MatchStatus } from '@/types/matches'

interface Props {
  row: ProductMappingRow
  isDeletingId: number | null
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'delete', mappingId: number): void
}>()

// ── Display helpers ──────────────────────────────────────────────

function formatPrice(product: ProductSummary | null | undefined): string {
  if (!product) return '—'
  const price = product.price
  if (price == null || price === '') return '—'
  const currency = product.currency ?? ''
  const num = typeof price === 'string' ? parseFloat(price) : price
  if (isNaN(num)) return String(price)
  return currency ? `${num.toFixed(2)} ${currency}` : num.toFixed(2)
}

function statusLabel(status: MatchStatus | null | undefined): string {
  if (status === 'confirmed') return '✅ підтверджено'
  if (status === 'rejected') return '✖ відхилено'
  return status ?? '—'
}

function scoreClass(confidence: number): string {
  const pct = Math.round(confidence * 100)
  if (pct >= 85) return ''
  if (pct >= 65) return 'medium'
  return 'low'
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('uk-UA', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  } catch {
    return iso.slice(0, 10)
  }
}
</script>

<style scoped>
.mw-row { vertical-align: middle; }
.cat-label {
  font-size: 0.76rem;
  color: var(--muted, #6b6f85);
  margin-top: 2px;
}
.link-btn {
  color: var(--accent, #5b5bd6);
  text-decoration: none;
  font-weight: 500;
}
.link-btn:hover { text-decoration: underline; }
.price-cell { font-variant-numeric: tabular-nums; white-space: nowrap; }
.score-cell { text-align: center; }
.date-cell  { font-size: 0.85rem; color: var(--muted); white-space: nowrap; }
.action-cell { text-align: center; }
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  background: #f1f1f1;
  color: #555;
}
.status-badge.confirmed { background: #d4f5e1; color: #1a6e38; }
.status-badge.rejected  { background: #fee2e2; color: #991b1b; }
.score-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  background: #e0f2ff;
  color: #1a4a8f;
}
.score-pill.medium { background: #fff3cd; color: #856404; }
.score-pill.low    { background: #fee2e2; color: #991b1b; }
</style>

