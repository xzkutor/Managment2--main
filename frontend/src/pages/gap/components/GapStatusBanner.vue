<template>
  <div
    v-if="refreshing"
    class="gap-surface-refreshing"
    role="status"
    aria-live="polite"
  >
    <span class="spinner" aria-hidden="true"></span> Оновлення…
  </div>

  <!-- Initial loading (no result yet) -->
  <div
    v-else-if="initialLoading"
    class="status-block info gap-surface-status"
    role="status"
    aria-live="polite"
  >
    <span class="spinner" aria-hidden="true"></span> Завантаження…
  </div>

  <!-- Error -->
  <div
    v-else-if="errorText"
    class="status-block error gap-surface-status"
    role="alert"
  >
    {{ errorText }}
  </div>

  <!-- Loaded-empty -->
  <div
    v-else-if="isEmpty"
    class="empty-state gap-surface-empty"
  >
    <div class="empty-state-icon">🔍</div>
    <div class="empty-state-title">Розрив відсутній</div>
    <div class="empty-state-body">Немає товарів, що задовольняють обрані фільтри.</div>
  </div>
</template>

<script setup lang="ts">
/**
 * GapStatusBanner.vue — in-surface workspace states (Commit 5).
 *
 * Three distinct render modes:
 *   refreshing      — reload in progress while a result is already displayed
 *   initialLoading  — very first load (no result to show behind it)
 *   errorText       — blocking API or store error
 *   isEmpty         — loaded, zero results
 */
import { computed } from 'vue'

interface Props {
  loading: boolean
  error: string | null
  isEmpty: boolean
  hasLoaded: boolean
  storesError: string | null
}

const props = withDefaults(defineProps<Props>(), {
  error: null,
  storesError: null,
})

/** Loading while a prior result is already visible → gentle "refreshing" bar */
const refreshing = computed(() => props.loading && props.hasLoaded)
/** Loading but no prior result → full loading block */
const initialLoading = computed(() => props.loading && !props.hasLoaded)
const errorText = computed(() => props.storesError ?? props.error)
</script>

<style scoped>
.gap-surface-refreshing {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--info-bg, #eff6ff);
  color: var(--info-text, #1e40af);
  border-radius: var(--radius-md);
  font-size: 0.88rem;
  margin-bottom: 12px;
}
.gap-surface-status {
  margin-bottom: 12px;
}
.gap-surface-empty {
  padding: 40px 20px;
}
</style>
