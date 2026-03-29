<template>
  <!-- Content only — outer shell provided by ComparisonCollapsibleSection in ComparisonPage -->
  <div
    v-for="m in suggestions"
    :key="`${m.reference_product?.id}:${m.target_product?.id}`"
    class="cw-suggestion-row"
  >
    <!-- Ref ──→ Target pair -->
    <div class="cw-suggestion-pair">
      <div class="cw-suggestion-product">
        <div>
          <ProductLink :product="m.reference_product" />
          <span class="badge badge-heuristic" style="margin-left:5px;">авто</span>
        </div>
        <div class="muted" style="font-size:0.8rem;">{{ formatPrice(m.reference_product) }}</div>
      </div>
      <span class="cw-suggestion-arrow">→</span>
      <div class="cw-suggestion-product">
        <div>
          <ProductLink :product="m.target_product" />
          <CatBadge :cat="m.target_category" />
        </div>
        <div class="muted" style="font-size:0.8rem;">{{ formatPrice(m.target_product) }}</div>
      </div>
      <ScorePill :percent="m.score_percent" :details="m.score_details" />
    </div>

    <!-- Icon-only actions -->
    <div class="cw-action-row">
      <button
        class="btn-icon-action confirm"
        :disabled="isInProgress(m.reference_product?.id, m.target_product?.id)"
        :title="isInProgress(m.reference_product?.id, m.target_product?.id) ? '…' : 'Підтвердити збіг'"
        :aria-label="'Підтвердити збіг: ' + (m.reference_product?.name ?? '')"
        @click="onConfirm(m)"
      >✔</button>
      <button
        class="btn-icon-action reject"
        :disabled="isInProgress(m.reference_product?.id, m.target_product?.id)"
        :title="isInProgress(m.reference_product?.id, m.target_product?.id) ? '…' : 'Відхилити пропозицію'"
        :aria-label="'Відхилити пропозицію: ' + (m.reference_product?.name ?? '')"
        @click="onReject(m)"
      >✖</button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * AutoSuggestionsTable.vue — high-confidence auto-suggestion rows (RFC-016 v2, Commits 4+6).
 * Outer shell provided by ComparisonCollapsibleSection; icon-only action buttons.
 */
import type { ConfirmedMatch, MatchStatus } from '../types'
import ProductLink from './shared/ProductLink.vue'
import CatBadge    from './shared/CatBadge.vue'
import ScorePill   from './shared/ScorePill.vue'
import { formatPrice } from './shared/format'

interface Props {
  suggestions:           ConfirmedMatch[]
  decisionInProgressKey: string | null
}
const props = withDefaults(defineProps<Props>(), {
  suggestions:           () => [],
  decisionInProgressKey: null,
})

const emit = defineEmits<{
  (e: 'decision', refId: number, tgtId: number, status: MatchStatus): void
}>()

function isInProgress(refId: number | undefined, tgtId: number | undefined): boolean {
  if (refId == null || tgtId == null) return false
  return props.decisionInProgressKey === `${refId}:${tgtId}`
}
function onConfirm(m: ConfirmedMatch) {
  if (m.reference_product?.id && m.target_product?.id)
    emit('decision', m.reference_product.id, m.target_product.id, 'confirmed')
}
function onReject(m: ConfirmedMatch) {
  if (m.reference_product?.id && m.target_product?.id)
    emit('decision', m.reference_product.id, m.target_product.id, 'rejected')
}
</script>
