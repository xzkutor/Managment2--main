<template>
  <!--
    Route-view wrapper for the Matches review page (/matches).

    MatchesPage is self-contained: initialises all state via useMatchesPage()
    which bootstraps stores immediately on creation. No external props or DOM
    globals required. Verified working under Vue Router control inside the
    preview SPA (Commit 7).
  -->
  <MatchesPage />
</template>

<script setup lang="ts">
import MatchesPage from './MatchesPage.vue'
</script>

