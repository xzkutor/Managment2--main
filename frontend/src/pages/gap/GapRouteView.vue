<template>
  <!--
    Route-view wrapper for the Gap review page (/gap).

    GapPage is self-contained: initialises filter/data/action state via
    composables, calls loadStores() in onMounted, load triggered manually by
    the user. No external props or DOM globals required. Verified working
    under Vue Router control inside the preview SPA (Commit 7).
  -->
  <GapPage />
</template>

<script setup lang="ts">
import GapPage from './GapPage.vue'
</script>

