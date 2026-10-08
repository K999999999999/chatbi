import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { defineConfig } from '@playwright/test';

if (process.env.CHATBI_CONTAINER_REAL_E2E !== '1') {
  throw new Error('本地部署真实浏览器验收必须显式开启');
}

const reportDir = process.env.CHATBI_CONTAINER_REPORT_DIR;
const credentialsFile = process.env.CHATBI_CONTAINER_CREDENTIALS_FILE;
if (!reportDir || !credentialsFile || resolve(credentialsFile) !== resolve(reportDir, 'credentials.env')) {
  throw new Error('本地部署验收凭证路径必须位于本次私有报告目录');
}

const credentials = new Map<string, string>();
for (const line of readFileSync(credentialsFile, 'utf8').split(/\r?\n/)) {
  if (!line || line.startsWith('#')) continue;
  const separator = line.indexOf('=');
  if (separator < 1) throw new Error('本地部署验收凭证文件格式无效');
  credentials.set(line.slice(0, separator), line.slice(separator + 1));
}
for (const name of ['CHATBI_REAL_E2E_USERNAME', 'CHATBI_REAL_E2E_PASSWORD', 'CHATBI_CONTAINER_REFERENCE']) {
  const value = credentials.get(name);
  if (!value) throw new Error('本地部署验收凭证缺少必需字段');
  process.env[name] = value;
}

export default defineConfig({
  testDir: './tests',
  testMatch: '**/container-real.spec.ts',
  grepInvert: /源码挂载实际触发 Python 重载与 Vite 热更新/,
  workers: 1,
  retries: 0,
  timeout: 1800000,
  reporter: './playwright.container-reporter.ts',
  outputDir: join(reportDir, 'playwright-results'),
  use: {
    baseURL: process.env.CHATBI_CONTAINER_BASE_URL,
    channel: 'msedge',
    viewport: { width: 1440, height: 1000 },
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
});
