<template>
  <!--
    AppShellLayout — SPA application shell.

    Structural composition (left-sidebar canonical navigation model):
      a.skip-link           ← keyboard skip-to-main-content
      .app-shell
        aside.app-shell-sidebar
          .app-shell-brand  ← product name / logo
          AppShellSidebarNav ← canonical app nav (left sidebar, NOT in header)
        .app-shell-content
          AppShellHeader    ← page title/subtitle from route.meta only
          <main #main-content>
            RouterView

    static/css/common.css provides all app-shell-* styles.
  -->
  <a href="#main-content" class="skip-link">Перейти до основного вмісту</a>
  <div class="app-shell">
    <aside class="app-shell-sidebar" aria-label="Навігація застосунку">
      <div class="app-shell-brand" aria-hidden="true">🏒 Pricewatch</div>
      <AppShellSidebarNav />
    </aside>
    <div class="app-shell-content">
      <AppShellHeader />
      <main id="main-content" tabindex="-1">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppShellHeader from '@/components/AppShellHeader.vue'
import AppShellSidebarNav from '@/components/AppShellSidebarNav.vue'
</script>

<style scoped>
/* Skip-to-content link — visible only on keyboard focus */
.skip-link {
  position: absolute;
  top: -9999px;
  left: 8px;
  z-index: 9999;
  padding: 8px 16px;
  background: #fff;
  color: #403ea3;
  font-weight: 700;
  border-radius: 4px;
  text-decoration: none;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.skip-link:focus {
  top: 8px;
}

main {
  flex: 1;
  padding: 28px 24px 64px;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

@media (max-width: 720px) {
  main {
    padding: 18px 16px 48px;
  }
}
</style>
