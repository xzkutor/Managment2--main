<template>
  <div>
    <!-- Error state -->
    <div v-if="errorText" class="status-block error" style="margin-bottom:14px;">
      {{ errorText }}
    </div>

    <!-- Comparing state -->
    <div v-else-if="comparing" class="status-block info" style="margin-bottom:14px;">
      <span class="spinner" />Виконується порівняння…
    </div>

    <!-- Result state -->
    <template v-else-if="result">
      <!-- Context strip -->
      <div v-if="referenceCategory || targetStore" class="cw-context-strip">
        <span>📂</span>
        <a
          v-if="referenceCategory && referenceCategory.url"
          class="cw-context-chip cw-context-chip--link"
          :href="referenceCategory.url"
          target="_blank"
          rel="noopener"
          :title="referenceCategory.url"
        >{{ referenceCategory.name }}</a>
        <span v-else-if="referenceCategory" class="cw-context-chip">{{ referenceCategory.name }}</span>
        <span v-if="targetStore" style="color:var(--muted);">→</span>
        <a
          v-if="targetStore && targetStore.base_url"
          class="cw-context-chip cw-context-chip--link"
          :href="targetStore.base_url"
          target="_blank"
          rel="noopener"
          :title="targetStore.base_url"
        >{{ targetStore.name }}</a>
        <span v-else-if="targetStore" class="cw-context-chip">{{ targetStore.name }}</span>
        <span v-else style="font-size:0.8rem;">всі цільові магазини</span>
      </div>

      <!-- KPI grid -->
      <div class="cw-kpi-grid">
        <div class="cw-kpi-card" :class="autoCount > 0 ? 'kpi-ok' : 'kpi-zero'">
          <div class="kpi-num">{{ autoCount }}</div>
          <div class="kpi-lbl">Авто-пропозиції</div>
        </div>
        <div class="cw-kpi-card" :class="result.summary.candidate_groups > 0 ? 'kpi-warn' : 'kpi-zero'">
          <div class="kpi-num">{{ result.summary.candidate_groups }}</div>
          <div class="kpi-lbl">Кандидати</div>
        </div>
        <div class="cw-kpi-card" :class="result.summary.reference_only > 0 ? 'kpi-warn' : 'kpi-zero'">
          <div class="kpi-num">{{ result.summary.reference_only }}</div>
          <div class="kpi-lbl">Тільки в референсі</div>
        </div>
        <div class="cw-kpi-card" :class="result.summary.target_only > 0 ? '' : 'kpi-zero'">
          <div class="kpi-num">{{ result.summary.target_only }}</div>
          <div class="kpi-lbl">Тільки в цільовому</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * ComparisonSummaryBar.vue — KPI-card result header for the comparison workspace.
 *
 * Replaces the old one-line text summary with four KPI cards (RFC-016, Commit 3).
 * Also displays a compact context strip when reference category / target store are known.
 */
import { computed } from 'vue'
import type { ComparisonResult } from '../types'
import type { CategorySummary } from '@/types/store'
import type { StoreSummary } from '@/types/store'

interface Props {
  result:            ComparisonResult | null
  comparing:         boolean
  errorText:         string | null
  referenceCategory: CategorySummary | null
  targetStore:       StoreSummary | null
}
const props = withDefaults(defineProps<Props>(), {
  result:            null,
  comparing:         false,
  errorText:         null,
  referenceCategory: null,
  targetStore:       null,
})


const autoCount = computed(() =>
  (props.result?.confirmed_matches ?? []).filter((m) => !m.is_confirmed).length,
)
</script>

