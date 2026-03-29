import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
//
// Single-entry SPA configuration for PriceWatch (Commit 9).
// The previous multi-entry build (src/entries/*.ts) has been collapsed into
// a single SPA entry: src/main.ts.
//
// Flask serves spa.html for all operator-facing routes; Vue Router owns
// client-side navigation. The manifest is still generated for production
// asset lookup by pricewatch/web/assets.py (vite_asset_tags helper).

export default defineConfig({
  plugins: [vue()],

  // Base public path — must match where Flask serves static/dist/.
  // Without this Vite emits dynamic import URLs as /assets/... which 404
  // because Flask serves them from /static/dist/assets/...
  base: '/static/dist/',

  build: {
    // Output to Flask's static directory so it can serve assets directly.
    // Vite 5 writes the manifest to <outDir>/.vite/manifest.json
    // → static/dist/.vite/manifest.json (matches VITE_MANIFEST_PATH default in app_factory.py)
    outDir: '../static/dist',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        // Single SPA entry — all operator routes are served by spa.html
        // and handled client-side by Vue Router.
        app: resolve(__dirname, 'src/main.ts'),
      },
    },
  },

  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
})

