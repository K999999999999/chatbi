import { defineConfig } from '@playwright/test';
import { randomBytes, randomUUID } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { captureSourceIdentity } from './test-support/source-identity';

if (process.env.CHATBI_REAL_E2E !== '1') throw new Error('真实浏览器验收必须显式开启');
process.umask(0o077);
process.env.CHATBI_REAL_E2E_USERNAME ??= `web-e2e-${Date.now()}`;
process.env.CHATBI_REAL_E2E_PASSWORD ??= randomBytes(24).toString('hex');
process.env.CHATBI_WEB_ORIGIN = 'http://127.0.0.1:18002';
process.env.CHATBI_WEB_DIST_DIR = 'frontend/dist';
process.env.CHATBI_TRACE_CONTENT_ENABLED = 'false';
const reportRoot = resolve('..', 'reports/browser-real');
const reportRunId = `${new Date().toISOString().replace(/[:.]/g, '-')}-${randomUUID()}`;
const runDirectory = resolve(reportRoot, 'runs', reportRunId);
mkdirSync(runDirectory, { recursive: true, mode: 0o700 });
process.env.CHATBI_REAL_E2E_REPORT_DIR = runDirectory;
process.env.CHATBI_REAL_E2E_RUN_ID = reportRunId;
writeFileSync(resolve(runDirectory, 'start.json'), JSON.stringify({
  run_id: reportRunId,
  started_at: new Date().toISOString(),
  source_start: captureSourceIdentity(resolve('..')),
}), { mode: 0o600, flag: 'wx' });
export default defineConfig({
  testDir: './tests', testMatch: '**/real.spec.ts', workers: 1, retries: 0, timeout: 1500000,
  reporter: './playwright.safe-reporter.ts', outputDir: resolve(runDirectory, 'playwright-results'),
  use: { baseURL: 'http://127.0.0.1:18002', channel: 'chrome',
    launchOptions: process.env.CHATBI_CHROME_PATH ? { executablePath: process.env.CHATBI_CHROME_PATH } : {},
    viewport: { width: 1440, height: 1000 }, trace: 'off', video: 'off', screenshot: 'off' },
  webServer: { command: 'uv run --locked uvicorn tests.browser_real_support:create_browser_real_app --factory --host 127.0.0.1 --port 18002',
    cwd: '..', url: 'http://127.0.0.1:18002/health', reuseExistingServer: false, timeout: 120000,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 30000 }, stdout: 'ignore', stderr: 'ignore' },
});
