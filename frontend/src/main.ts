/**
 * SPA entry point — mounts the single Vue application.
 *
 * Commit 9: This is the sole Vite build entry (key "app" in rollupOptions.input).
 * The previous multi-entry build (src/entries/*) has been removed.
 * Flask serves spa.html for all operator-facing routes; Vue Router owns
 * client-side navigation. Loaded via vite_asset_tags('src/main.ts') in spa.html.
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'
import App from '@/App.vue'
import '@/styles/base.css'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)

app.mount('#app')

