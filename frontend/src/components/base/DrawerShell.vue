<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="drawer-backdrop"
      role="presentation"
      @click.self="$emit('close')"
      @keydown.esc="$emit('close')"
    >
      <div
        class="drawer-panel"
        role="dialog"
        :aria-modal="true"
        aria-labelledby="drawer-panel-title"
      >
        <!-- Header -->
        <div class="drawer-header">
          <span id="drawer-panel-title" class="drawer-title">
            <slot name="title">{{ title }}</slot>
          </span>
          <button
            class="btn-ghost btn-sm drawer-close"
            type="button"
            aria-label="Закрити"
            @click="$emit('close')"
          >✕</button>
        </div>

        <!-- Body -->
        <div class="drawer-body">
          <slot />
        </div>

        <!-- Footer -->
        <div v-if="$slots.footer" class="drawer-footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * DrawerShell.vue — reusable right-side slide-in drawer primitive.
 *
 * Renders via <Teleport to="body"> above the page.
 * Closes on backdrop click and Escape key.
 * Slots: default (body), title, footer.
 */
interface Props {
  open: boolean
  title?: string
}
withDefaults(defineProps<Props>(), { title: '' })
defineEmits<{ (e: 'close'): void }>()
</script>

