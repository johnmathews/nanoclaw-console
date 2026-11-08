import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import vueDevTools from 'vite-plugin-vue-devtools'
import { APP_NAME } from './src/lib/app.ts'

// In development the API runs separately on :8000 (docs/development.md); the browser still sees
// one origin, as it does in production, where the API process serves the built files itself.
const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000'
const apiProxy = { '/api': apiUrl, '/healthz': apiUrl }

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    // The e2e suite (playwright.config.ts) sets PLAYWRIGHT: the DevTools overlay is UI the app
    // doesn't have, and axe would measure it.
    process.env.PLAYWRIGHT ? null : vueDevTools(),
    // The page title is the app's one name (src/lib/app.ts), written into index.html.
    {
      name: 'app-name',
      transformIndexHtml: {
        order: 'pre',
        handler: (html) => html.replaceAll('%APP_NAME%', APP_NAME),
      },
    },
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
})
