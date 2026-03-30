<template>
  <div class="gap-kpi-header">

    <!-- Context strip: what is being queried -->
    <div v-if="targetStoreName || refCategoryName" class="gap-kpi-context">
      <span class="gap-kpi-context-label">📂 Розрив:</span>
      <span v-if="refCategoryName" class="gap-kpi-chip">{{ refCategoryName }}</span>
      <span v-if="refCategoryName && targetStoreName" class="gap-kpi-sep">→</span>
      <span v-if="targetStoreName" class="gap-kpi-chip gap-kpi-chip--target">{{ targetStoreName }}</span>
      <span v-if="targetCatCount != null" class="gap-kpi-chip gap-kpi-chip--count">
        {{ targetCatCount }} {{ targetCatCount === 1 ? 'категорія' : (targetCatCount < 5 ? 'категорії' : 'категорій') }}
      </span>
    </div>

    <!-- KPI cards -->
    <div class="gap-kpi-grid">
      <div class="gap-kpi-card">
        <div class="gap-kpi-num">{{ summary.total }}</div>
        <div class="gap-kpi-lbl">Усього</div>
      </div>
      <div class="gap-kpi-card gap-kpi-card--new">
        <div class="gap-kpi-num">{{ summary.new }}</div>
        <div class="gap-kpi-lbl">Нові</div>
      </div>
      <div class="gap-kpi-card gap-kpi-card--in-progress">
        <div class="gap-kpi-num">{{ summary.in_progress }}</div>
        <div class="gap-kpi-lbl">В роботі</div>
      </div>
      <div class="gap-kpi-card gap-kpi-card--done">
        <div class="gap-kpi-num">{{ summary.done }}</div>
        <div class="gap-kpi-lbl">Опрацьовано</div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
/**
 * GapSummary.vue — compact workspace KPI strip with query context header (Commit 4).
 * Replaces the loose summary-row with a tighter header block that also shows
 * which store/category is being compared.
 */
import type { GapSummary } from '@/types/gap'

interface Props {
  summary: GapSummary
  /** Name of the selected target store (for context display). */
  targetStoreName?: string | null
  /** Name of the selected reference category (for context display). */
  refCategoryName?: string | null
  /** Number of selected mapped target categories. */
  targetCatCount?: number | null
}
withDefaults(defineProps<Props>(), {
  targetStoreName: null,
  refCategoryName: null,
  targetCatCount: null,
})
</script>

<style scoped>
.gap-kpi-header {
  background: var(--panel);
  border-radius: var(--radius-xl);
  padding: 16px 20px;
  box-shadow: 0 4px 14px rgba(82,86,133,0.08);
  margin-bottom: 16px;
}
.gap-kpi-context {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 0.82rem;
  color: var(--muted);
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.gap-kpi-context-label { font-weight: 600; }
.gap-kpi-chip {
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 2px 10px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text);
}
.gap-kpi-chip--target { color: var(--accent); }
.gap-kpi-chip--count { color: var(--muted); font-weight: 500; }
.gap-kpi-sep { color: var(--muted); }
.gap-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
.gap-kpi-card {
  text-align: center;
  padding: 10px 8px;
  border-radius: var(--radius-lg);
  background: #f8f9ff;
  border: 1px solid var(--border);
}
.gap-kpi-num {
  font-size: 1.6rem;
  font-weight: 800;
  line-height: 1;
  color: var(--accent);
}
.gap-kpi-lbl {
  font-size: 0.72rem;
  color: var(--muted);
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.gap-kpi-card--new .gap-kpi-num       { color: #1a4a8f; }
.gap-kpi-card--in-progress .gap-kpi-num { color: #d97706; }
.gap-kpi-card--done .gap-kpi-num      { color: #059669; }
</style>
