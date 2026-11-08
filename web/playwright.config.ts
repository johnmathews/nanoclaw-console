import { defineConfig, devices } from '@playwright/test'

// The browser checks (e2e/): axe in both themes and no sideways scroll at phone width, against the
// production build served by `vite preview`. The app's /api is mocked per test (e2e/support.ts), so
// no API server runs. PLAYWRIGHT=1 keeps the Vue DevTools plugin out of the build (vite.config.ts).
const PORT = 4179

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['github']] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run build-only && npm run preview -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    env: { PLAYWRIGHT: '1' },
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
