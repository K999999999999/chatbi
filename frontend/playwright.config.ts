import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', testIgnore: ['**/real.spec.ts', '**/dev.spec.ts', '**/container-real.spec.ts'], workers: 1, retries: 0,
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:18001', channel: 'chrome',
    launchOptions: process.env.CHATBI_CHROME_PATH ? { executablePath: process.env.CHATBI_CHROME_PATH } : {},
    viewport: { width: 1440, height: 1000 }, trace: 'off', video: 'off', screenshot: 'off' },
  webServer: { command: 'uv run --locked uvicorn tests.browser_support:create_browser_app --factory --host 127.0.0.1 --port 18001',
    cwd: '..', url: 'http://127.0.0.1:18001/health', reuseExistingServer: false },
});
