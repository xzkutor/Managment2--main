<template>
  <!--
    ServicePage.vue — DEPRECATED: superseded by ServiceRouteView.vue.

    The service console is now route-addressable via /service/* child routes.
    ServiceRouteView.vue owns the left section rail + <RouterView> outlet.
    This file is retained only as a historical artefact; it is not mounted
    by any active route or entry point.
  -->
  <div class="service-page--legacy" />
</template>

<script setup lang="ts">
/**
 * @deprecated
 * Superseded by ServiceRouteView.vue as part of service-console-redesign (ADR-0019).
 * The old top-tab + v-show model has been replaced with route-addressable sections.
 * See: frontend/src/pages/service/ServiceRouteView.vue
 */
</script>

