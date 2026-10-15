import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './apps/web/e2e', timeout: 45_000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:3081', browserName: 'chromium', channel: 'msedge', headless: true, trace: 'retain-on-failure' },
  webServer: { command: 'node scripts/start.mjs --no-open --port 3081', url: 'http://127.0.0.1:3081/api/health', timeout: 90_000, reuseExistingServer: false,
    env: { ZHANGWEN_DATA_DIR: '.test-data/e2e-' + Date.now(), ZHANGWEN_DEEPSEEK_API_KEY: '' } },
});
