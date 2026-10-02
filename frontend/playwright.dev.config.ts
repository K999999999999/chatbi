import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', testMatch: '**/dev.spec.ts', workers: 1, retries: 0, timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:5173', channel: 'chrome',
    launchOptions: process.env.CHATBI_CHROME_PATH ? { executablePath: process.env.CHATBI_CHROME_PATH } : {},
    viewport: { width: 1440, height: 1000 }, trace: 'off', video: 'off', screenshot: 'off' },
  webServer: [
    { command: 'uv run --locked uvicorn tests.browser_support:create_browser_app --factory --host 127.0.0.1 --port 8000',
      cwd: '..', env: { CHATBI_BROWSER_TEST_ORIGIN: 'http://127.0.0.1:5173' }, url: 'http://127.0.0.1:8000/health', reuseExistingServer: false },
    { command: 'npm run dev', url: 'http://127.0.0.1:5173', reuseExistingServer: false },
  ],
});
