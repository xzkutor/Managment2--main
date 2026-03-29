<template>
  <!--
    Route-view wrapper for the Service Console (/service).

    ServicePage is self-contained: tab state via useServiceTabs(), all tab
    islands via v-show. enableAdminSync read via useBootstrapConfig() — no
    raw SERVICE_CONFIG global dependency. Verified working under Vue Router
    control inside the preview SPA (Commit 7).
  -->
  <ServicePage />
</template>

<script setup lang="ts">
import ServicePage from './ServicePage.vue'
</script>

