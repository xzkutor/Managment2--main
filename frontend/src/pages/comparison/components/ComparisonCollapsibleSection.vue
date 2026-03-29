<template>
  <div class="cw-section">
    <button
      class="cw-collapsible-header"
      type="button"
      :aria-expanded="expanded"
      @click="emit('toggle')"
    >
      <span class="cw-section-title">
        {{ title }}
        <span :class="['badge', badgeClass]">{{ count }}</span>
      </span>
      <span class="cw-chevron" aria-hidden="true">▼</span>
    </button>
    <div v-show="expanded" class="cw-collapsible-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ComparisonCollapsibleSection.vue — shared collapsible section shell (RFC-016 v2, Commit 4).
 *
 * Provides the outer cw-section card with a toggle-able header row.
 * Inner content is provided via the default slot.
 * Three primary review sections use this: AutoSuggestions, CandidateGroups, ReferenceOnly.
 */
interface Props {
  title:       string
  count:       number
  expanded:    boolean
  badgeClass?: string
}
withDefaults(defineProps<Props>(), {
  badgeClass: 'badge-ambig',
})

const emit = defineEmits<{
  (e: 'toggle'): void
}>()
</script>

