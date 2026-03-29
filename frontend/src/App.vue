<template>
  <!--
    Root SPA component.
    AppShellLayout owns the shared header/nav chrome and the RouterView outlet.
    See frontend/src/layouts/AppShellLayout.vue and
        frontend/src/components/AppShellHeader.vue.
  -->
  <AppShellLayout />
</template>

<script setup lang="ts">
import AppShellLayout from '@/layouts/AppShellLayout.vue'
</script>

