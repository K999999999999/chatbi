import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { login, send } from './helpers';
import { queryResult } from '../src/results';

test('源码挂载实际触发 Python 重载与 Vite 热更新', async ({ page }) => {
  const backend = '/workspace/backend-src/query_api/app.py';
  const css = '/workspace/frontend/src/style.css';
  const originalBackend = readFileSync(backend, 'utf8');
  const originalCss = readFileSync(css, 'utf8');
  const marker = 'return {"status": "ok"}';
  expect(originalBackend.split(marker).length).toBe(2);
  const changedBackend = originalBackend.replace(marker, 'return {"status": "hot-reload-check"}');
  const changedCss = `${originalCss}\nbody { --chatbi-hot-check: 1; }\n`;
  await page.goto('/');
  try {
    writeFileSync(backend, changedBackend);
    await expect.poll(async () => {
      try { return (await (await page.request.get('/health')).json()).status; } catch { return 'restarting'; }
    }, { timeout: 60000 }).toBe('hot-reload-check');
    writeFileSync(css, changedCss);
    await expect.poll(() => page.evaluate(() => getComputedStyle(document.body).getPropertyValue('--chatbi-hot-check').trim()),
      { timeout: 30000 }).toBe('1');
    writeFileSync('/reports/hot-reload.json', JSON.stringify({
      commit: process.env.CHATBI_CONTAINER_COMMIT, experiment_dirty: true,
      python_reload: true, vite_hmr: true,
    }));
  } finally {
    let concurrentChange = false;
    if (readFileSync(backend, 'utf8') === changedBackend) writeFileSync(backend, originalBackend);
    else concurrentChange = true;
    const currentCss = readFileSync(css, 'utf8');
    if (currentCss === changedCss) writeFileSync(css, originalCss);
    else if (currentCss !== originalCss) concurrentChange = true;
    if (concurrentChange) throw new Error('源码被并发修改，已恢复可安全恢复的文件并保留现场');
  }
  await expect.poll(async () => {
    try { return (await (await page.request.get('/health')).json()).status; } catch { return 'restarting'; }
  }, { timeout: 60000 }).toBe('ok');
});

test('实际 Compose 网页登录 → 真实问数 → 同一对话追问', async ({ page, browser }) => {
  const reference = JSON.parse(process.env.CHATBI_CONTAINER_REFERENCE!);
  const evidence: Record<string, unknown> = {
    commit: process.env.CHATBI_CONTAINER_COMMIT, git_dirty: process.env.CHATBI_CONTAINER_GIT_DIRTY === 'true',
    username: process.env.CHATBI_REAL_E2E_USERNAME, reference,
    at: new Date().toISOString(), browser: browser.version(), target: 'compose-vite-api',
  };
  try {
    await login(page, process.env.CHATBI_REAL_E2E_USERNAME!, process.env.CHATBI_REAL_E2E_PASSWORD!);
    const firstResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/query'), { timeout: 240000 });
    await send(page, '2025年2月已完成订单的人民币净销售额是多少？');
    const firstHttp = await firstResponse;
    const firstPayload = await firstHttp.json();
    evidence.first_http_status = firstHttp.status();
    evidence.first_error_code = firstPayload.error_code;
    const first = queryResult(firstPayload);
    expect(first.rows.length).toBe(1);
    expect(Number(first.rows[0][0])).toBe(Number(reference.net_sales['2']));
    await expect(page.getByRole('table')).toBeVisible();
    const secondResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/query'), { timeout: 240000 });
    await send(page, '改成2025年3月');
    const second = queryResult(await (await secondResponse).json());
    expect(second.conversation_id).toBe(first.conversation_id);
    expect(Number(second.rows[0][0])).toBe(Number(reference.net_sales['3']));
    evidence.query = { value: first.rows[0][0], conversation_id: first.conversation_id };
    evidence.followup = { value: second.rows[0][0], conversation_id: second.conversation_id };
    evidence.status = 'passed';
    await page.getByRole('button', { name: '退出登录' }).click();
    await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  } finally {
    writeFileSync('/reports/browser.json', JSON.stringify(evidence, null, 2));
  }
});
