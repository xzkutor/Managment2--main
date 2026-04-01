<template>
  <!--
    ServiceRouteView.vue — service console shell (service-console-redesign).

    Renders the sticky left section-navigation rail and the right workspace
    <RouterView> outlet. Each service section (categories, mappings, scheduler,
    history) mounts independently via its own route — only the active section
    is mounted at any time.

    Route: /service (parent, redirects to /service/categories)
  -->
  <div class="sc-workspace">

    <!-- ── Left section rail ─────────────────────────────── -->
    <aside class="sc-rail" aria-label="Service Console navigation">
      <div class="sc-rail-heading">Service Console</div>
      <nav class="sc-rail-nav">
        <RouterLink
          v-for="s in SERVICE_SECTIONS"
          :key="s.id"
          :to="{ name: s.routeName }"
          class="sc-rail-item"
          active-class="sc-rail-item--active"
        >
          <span class="sc-rail-icon" aria-hidden="true">{{ s.icon }}</span>
          {{ s.label }}
        </RouterLink>
      </nav>
    </aside>

    <!-- ── Right workspace: route-driven section ─────────── -->
    <main class="sc-workspace-main">
      <RouterView />
    </main>

  </div>
</template>

<script setup lang="ts">
/**
 * ServiceRouteView.vue — route-addressable service console shell.
 *
 * The shell renders the left section rail and delegates the section content
 * to <RouterView>. Each section is lazy-loaded only when navigated to.
 * No v-show tab persistence — inactive sections are not mounted.
 */
import { RouterLink, RouterView } from 'vue-router'
import { SERVICE_SECTIONS } from './composables/useServiceSections'
</script>
