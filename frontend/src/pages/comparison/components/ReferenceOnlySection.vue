<template>
  <!-- Content only — outer shell provided by ComparisonCollapsibleSection in ComparisonPage -->
  <p v-if="!items.length" class="muted">Немає товарів тільки в референсі.</p>
  <div
    v-for="item in items"
    :key="item.reference_product?.id ?? String(Math.random())"
    class="cw-review-card"
  >
    <div class="cw-ref-row">
      <ProductLink :product="item.reference_product" />
      <span class="muted" style="font-size:0.85rem;">{{ formatPrice(item.reference_product) }}</span>
      <div class="cw-action-row">
        <button
          v-if="item.reference_product"
          class="btn-icon-action pick"
          :title="'Вибрати відповідник для: ' + (item.reference_product?.name ?? '')"
          :aria-label="'Вибрати відповідник для: ' + (item.reference_product?.name ?? '')"
          @click="emit('open-picker', item.reference_product!)"
        >🔍</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ReferenceOnlySection.vue — reference-only items (RFC-016 v2, Commits 4+5).
 * Outer shell provided by ComparisonCollapsibleSection.
 * Pick trigger is in the header row; emits open-picker.
 */
import type { ReferenceOnlyItem, ComparisonProduct } from '../types'
import ProductLink from './shared/ProductLink.vue'
import { formatPrice } from './shared/format'

interface Props { items: ReferenceOnlyItem[] }
withDefaults(defineProps<Props>(), { items: () => [] })

const emit = defineEmits<{
  (e: 'open-picker', refProduct: ComparisonProduct): void
}>()
</script>
