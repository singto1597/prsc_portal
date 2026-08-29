import { defineConfig, devices } from '@playwright/test'

/**
 * E2E config เฉพาะ PIRI Boards flow (headless chromium — รันบน CI/เครื่องได้เลย)
 * - ต้องการ backend รันอยู่ที่ http://localhost:8000 (ชี้ e2e_piri_db + seed users แล้ว)
 * - เปิด VITE_API_BASE_URL ให้ frontend เรียก backend ท้องถิ่น (แทน .env ที่ชี้ prod)
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  retries: 0,
  workers: 1,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'VITE_API_BASE_URL=http://localhost:8000 npm run dev',
    port: 5173,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
