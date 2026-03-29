<template>
  <!--
    AppShellHeader — page heading component.

    Renders the per-route title and optional subtitle driven by route.meta.
    Does NOT own canonical app navigation — that responsibility belongs to
    AppShellSidebarNav (see frontend/src/components/AppShellSidebarNav.vue).
  -->
  <header class="app-shell-header">
    <div class="app-shell-title">{{ title }}</div>
    <div v-if="subtitle" class="app-shell-subtitle">{{ subtitle }}</div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const title = computed<string>(
  () => (route.meta.title as string | undefined) ?? 'Pricewatch',
)
const subtitle = computed<string | undefined>(
  () => route.meta.subtitle as string | undefined,
)
</script>

