<template>
  <!--
    ComparisonWorkspacePlaceholder.vue — shown in the main workspace area
    when no compare run has been executed yet (comparisonWorkspaceState === 'idle').

    Fills the otherwise empty right panel on wide monitors and guides the
    operator through the three-step workflow.
  -->
  <div class="cw-workspace-placeholder" role="status" aria-live="polite">
    <div class="cw-placeholder-icon" aria-hidden="true">📊</div>
    <div class="cw-placeholder-title">Готово до порівняння</div>
    <div class="cw-placeholder-body">
      Оберіть <strong>референсну категорію</strong> у лівій панелі,
      за потреби вкажіть <strong>цільовий магазин</strong>,
      а потім натисніть <strong>▶ Порівняти</strong>.
    </div>
    <div v-if="canCompare" class="cw-placeholder-hint">
      ✅ Усе готово — можна запускати порівняння.
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ComparisonWorkspacePlaceholder.vue — pre-compare placeholder for the main workspace.
 *
 * Rendered by ComparisonPage when comparisonWorkspaceState === 'idle' (no compare
 * has been triggered yet in the current session). Disappears as soon as a compare
 * starts or results are loaded.
 */
interface Props {
  /** True when canCompare from useComparisonPage is true (all preconditions met). */
  canCompare?: boolean
}
withDefaults(defineProps<Props>(), { canCompare: false })
</script>

<style scoped>
.cw-workspace-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 56px 24px;
  text-align: center;
  color: var(--muted);
  min-height: 260px;
}
.cw-placeholder-icon {
  font-size: 3rem;
  margin-bottom: 16px;
  line-height: 1;
}
.cw-placeholder-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 10px;
}
.cw-placeholder-body {
  font-size: 0.92rem;
  color: var(--muted);
  max-width: 380px;
  line-height: 1.6;
  margin-bottom: 14px;
}
.cw-placeholder-hint {
  font-size: 0.88rem;
  color: var(--success-text, #065f46);
  background: var(--success-bg, #d1fae5);
  padding: 6px 16px;
  border-radius: var(--radius-pill, 999px);
  font-weight: 600;
}
</style>

