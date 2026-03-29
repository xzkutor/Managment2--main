<template>
  <div class="mw-kpi-bar">
    <div class="mw-kpi-card">
      <div class="num">{{ total }}</div>
      <div class="lbl">Знайдено</div>
    </div>
    <div class="mw-kpi-card kpi-ok">
      <div class="num">{{ confirmed }}</div>
      <div class="lbl">Підтверджено</div>
    </div>
    <div class="mw-kpi-card kpi-warn">
      <div class="num">{{ rejected }}</div>
      <div class="lbl">Відхилено</div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * MatchesSummary.vue — KPI bar for the /matches workspace header.
 * Shows total, confirmed and rejected counts derived from the current page.
 * Rendered only when MatchesPage has loaded at least once (v-if on parent).
 */
interface Props {
  total: number
  confirmed: number
  rejected: number
}

defineProps<Props>()
</script>
