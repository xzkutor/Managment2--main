<template>
  <!--
    AppShellSidebarNav — canonical application navigation component.

    Owns all operator-facing navigation links. Uses RouterLink for fully
    client-side transitions. Active-link state uses exact-active-class only
    so the "/" link is not highlighted on every page (prefix-match suppressed).

    Link definitions are imported from @/constants/navigation — do not
    duplicate the route list here or in AppShellHeader.
  -->
  <nav class="app-shell-sidebar-nav" aria-label="Основна навігація">
    <RouterLink
      v-for="link in NAV_LINKS"
      :key="link.to"
      :to="link.to"
      class="app-shell-sidebar-link"
      active-class=""
      exact-active-class="active"
      :aria-current="isExact(link.to) ? 'page' : undefined"
    >
      {{ link.label }}
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { NAV_LINKS } from '@/constants/navigation'

const route = useRoute()

/** True when the current path exactly matches the given link target. */
function isExact(to: string): boolean {
  return route.path === to
}
</script>

