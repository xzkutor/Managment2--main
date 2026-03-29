<template>
  <!--
    NotFoundPage — client-side 404 screen.

    Rendered by Vue Router for any path that does not match a known SPA route.
    Flask's history-mode catch-all (ui_routes.py) serves spa.html for unknown
    paths so Vue Router receives control; this component handles the final render.
  -->
  <div class="not-found">
    <div class="not-found__code">404</div>
    <h1 class="not-found__title">Сторінку не знайдено</h1>
    <p class="not-found__message">
      За адресою <code class="not-found__path">{{ route.path }}</code> нічого немає.
    </p>
    <RouterLink to="/" class="not-found__home-link">← На головну</RouterLink>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
  gap: 12px;
}

.not-found__code {
  font-size: 6rem;
  font-weight: 700;
  line-height: 1;
  color: var(--color-border, #d0d5dd);
}

.not-found__title {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
}

.not-found__message {
  color: var(--color-text-muted, #667085);
  margin: 0;
}

.not-found__path {
  font-family: monospace;
  background: var(--color-surface-alt, #f2f4f7);
  padding: 1px 6px;
  border-radius: 4px;
}

.not-found__home-link {
  margin-top: 16px;
  color: var(--color-accent, #1d6cf0);
  text-decoration: none;
  font-weight: 500;
}

.not-found__home-link:hover {
  text-decoration: underline;
}
</style>

