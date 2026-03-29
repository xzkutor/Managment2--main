<template>
  <!--
    Route-view wrapper for the Comparison page (/).

    ComparisonPage is self-contained: it initialises all state via
    useComparisonPage() and triggers loadStores() in onMounted. No external
    props or DOM globals required. Verified working under Vue Router control
    inside the preview SPA (Commit 7).
  -->
  <ComparisonPage />
</template>

<script setup lang="ts">
import ComparisonPage from './ComparisonPage.vue'
</script>

