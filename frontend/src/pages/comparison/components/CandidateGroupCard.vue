<template>
  <div class="cw-review-card">
    <!-- Reference product header row: name + price + manual-pick trigger -->
    <div class="cw-ref-row">
      <ProductLink :product="group.reference_product" />
      <span class="muted" style="font-size:0.85rem;">{{ formatPrice(group.reference_product) }}</span>
      <div class="cw-action-row">
        <button
          v-if="group.reference_product"
          class="btn-icon-action pick"
          :title="'Вибрати вручну для: ' + (group.reference_product?.name ?? '')"
          :aria-label="'Вибрати вручну для: ' + (group.reference_product?.name ?? '')"
          @click="emit('open-picker', group.reference_product!)"
        >🔍</button>
      </div>
    </div>

    <!-- Candidate items -->
    <div
      v-for="c in group.candidates"
      :key="c.target_product?.id ?? String(Math.random())"
      class="cw-candidate-item"
    >
      <ProductLink :product="c.target_product" />
      <CatBadge :cat="c.target_category" />
      <span class="muted" style="font-size:0.82rem;">{{ formatPrice(c.target_product) }}</span>
      <ScorePill :percent="c.score_percent" :details="c.score_details" />

      <div class="cw-action-row">
        <!-- Accept / disabled -->
        <button
          v-if="c.can_accept !== false"
          class="btn-icon-action confirm"
          :disabled="isInProgress(c.target_product?.id)"
          :title="isInProgress(c.target_product?.id) ? '…' : 'Прийняти кандидата'"
          :aria-label="'Прийняти: ' + (c.target_product?.name ?? '')"
          @click="c.target_product && onAccept(c.target_product.id)"
        >✔</button>
        <button
          v-else
          class="btn-icon-action confirm"
          disabled
          title="Вже використано в іншому зіставленні"
        >🚫</button>

        <!-- Reject -->
        <button
          class="btn-icon-action reject"
          :disabled="isInProgress(c.target_product?.id)"
          :title="isInProgress(c.target_product?.id) ? '…' : 'Відхилити кандидата'"
          :aria-label="'Відхилити: ' + (c.target_product?.name ?? '')"
          @click="c.target_product && onReject(c.target_product.id)"
        >✖</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * CandidateGroupCard.vue — compact candidate group card (RFC-016 v2, Commits 5+6).
 *
 * Manual-pick trigger moved to the reference-product header row.
 * Confirm/reject are icon-only buttons with tooltip/aria-label.
 */
import type { CandidateGroup, MatchStatus, ComparisonProduct } from '../types'
import ProductLink from './shared/ProductLink.vue'
import CatBadge    from './shared/CatBadge.vue'
import ScorePill   from './shared/ScorePill.vue'
import { formatPrice } from './shared/format'

interface Props {
  group:                 CandidateGroup
  decisionInProgressKey: string | null
}
const props = withDefaults(defineProps<Props>(), {
  decisionInProgressKey: null,
})

const emit = defineEmits<{
  (e: 'decision',    refId: number, tgtId: number, status: MatchStatus): void
  (e: 'open-picker', refProduct: ComparisonProduct):                      void
}>()

function isInProgress(tgtId: number | undefined): boolean {
  if (tgtId == null || !props.group.reference_product?.id) return false
  return props.decisionInProgressKey === `${props.group.reference_product.id}:${tgtId}`
}
function onAccept(tgtId: number) {
  if (props.group.reference_product?.id)
    emit('decision', props.group.reference_product.id, tgtId, 'confirmed')
}
function onReject(tgtId: number) {
  if (props.group.reference_product?.id)
    emit('decision', props.group.reference_product.id, tgtId, 'rejected')
}
</script>
