<template>
  <!--
    GapPreRunPlaceholder.vue — workspace placeholder shown before the first
    gap query is executed. Fills the right workspace surface and guides the
    operator through the four-step workflow.
  -->
  <div class="gap-workspace-placeholder" role="status" aria-live="polite">
    <div class="gap-placeholder-icon" aria-hidden="true">🏒</div>
    <div class="gap-placeholder-title">Готово до аналізу розриву</div>
    <div class="gap-placeholder-body">
      Щоб знайти товари, які є у цільовому магазині, але відсутні у вашому каталозі:
    </div>
    <ol class="gap-placeholder-steps">
      <li>Оберіть <strong>цільовий магазин</strong> у лівій панелі</li>
      <li>Оберіть <strong>референсну категорію</strong></li>
      <li>Перевірте прив'язані <strong>цільові категорії</strong></li>
      <li>Натисніть <strong>Показати розрив</strong></li>
    </ol>
    <div v-if="canLoad" class="gap-placeholder-hint">
      ✅ Усе готово — можна запускати запит.
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * GapPreRunPlaceholder.vue — pre-run placeholder for the /gap workspace.
 *
 * Rendered inside the right workspace area when hasNeverLoaded === true.
 * Disappears once loading starts or a result is available.
 */
interface Props {
  /** True when canLoad from useGapFilters is true (all preconditions met). */
  canLoad?: boolean
}
withDefaults(defineProps<Props>(), { canLoad: false })
</script>

<style scoped>
.gap-workspace-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 56px 24px 40px;
  color: var(--muted);
  min-height: 280px;
  justify-content: center;
}
.gap-placeholder-icon {
  font-size: 3rem;
  margin-bottom: 16px;
  line-height: 1;
}
.gap-placeholder-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 10px;
}
.gap-placeholder-body {
  font-size: 0.92rem;
  color: var(--muted);
  max-width: 380px;
  line-height: 1.6;
  margin-bottom: 14px;
}
.gap-placeholder-steps {
  text-align: left;
  font-size: 0.9rem;
  color: var(--text);
  max-width: 320px;
  margin: 0 0 16px;
  padding-left: 20px;
  line-height: 1.9;
}
.gap-placeholder-steps li { margin-bottom: 2px; }
.gap-placeholder-hint {
  font-size: 0.88rem;
  color: var(--success-text, #065f46);
  background: var(--success-bg, #d1fae5);
  padding: 6px 18px;
  border-radius: var(--radius-pill, 999px);
  font-weight: 600;
}
</style>

