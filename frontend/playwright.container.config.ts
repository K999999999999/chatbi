import { defineConfig } from '@playwright/test';

if (process.env.CHATBI_CONTAINER_REAL_E2E !== '1') throw new Error('容器真实验收必须显式开启');
export default defineConfig({
  testDir: './tests', testMatch: '**/container-real.spec.ts', workers: 1, retries: 0, timeout: 600000,
  reporter: './playwright.container-reporter.ts', outputDir: '/tmp/playwright-results',
  use: { baseURL: process.env.CHATBI_CONTAINER_BASE_URL ?? 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 1000 }, trace: 'off', video: 'off', screenshot: 'off',
    launchOptions: { args: ['--no-sandbox'] } },
});
