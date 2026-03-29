<template>
  <!-- Content only — outer shell provided by ComparisonCollapsibleSection in ComparisonPage -->
  <p v-if="!groups.length" class="muted">Немає груп кандидатів.</p>
  <CandidateGroupCard
    v-for="g in groups"
    :key="g.reference_product?.id ?? String(Math.random())"
    :group="g"
    :decision-in-progress-key="decisionInProgressKey"
    @decision="(refId, tgtId, status) => emit('decision', refId, tgtId, status)"
    @open-picker="(refProduct) => emit('open-picker', refProduct)"
  />
</template>

<script setup lang="ts">
/**
 * CandidateGroups.vue — candidate group cards (RFC-016 v2, Commit 4).
 * Outer shell provided by ComparisonCollapsibleSection; propagates open-picker.
 */
import type { CandidateGroup, MatchStatus, ComparisonProduct } from '../types'
import CandidateGroupCard from './CandidateGroupCard.vue'

interface Props {
  groups:                CandidateGroup[]
  decisionInProgressKey: string | null
}
withDefaults(defineProps<Props>(), {
  groups:                () => [],
  decisionInProgressKey: null,
})

const emit = defineEmits<{
  (e: 'decision',    refId: number, tgtId: number, status: MatchStatus): void
  (e: 'open-picker', refProduct: ComparisonProduct):                      void
}>()
</script>
