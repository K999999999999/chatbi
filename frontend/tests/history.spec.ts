import { test, expect } from '@playwright/test';

const id = '00000000-0000-4000-8000-000000000001';
const tid = '00000000-0000-4000-8000-000000000002';
const header = { id, kind: 'query', title: '已保存的问数', first_question: '销售额', context_revision: 1,
  record_revision: 2, active: false, can_continue: true, can_resume: false, last_success_turn_id: tid, analysis_run_id: null };
const turn = { id: tid, history_id: id, ordinal: 1, question: '销售额', status: 'succeeded', public_error: null,
  snapshot: { request_id: 'saved-r', sql: 'SELECT 12', columns: ['销售额'], rows: [['12.50']], row_count: 1, truncated: false } };

test('刷新按URL读取已保存快照，不触发执行', async ({ page }) => {
  let writes = 0;
  await page.route('**/auth/browser/me', route => route.fulfill({ json: { user_id: 1, username: 'analyst', permissions: ['query.execute'], must_change_password: false } }));
  await page.route('**/api/v1/histories**', route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET') writes++;
    const value = path.endsWith(`/turns/${tid}`) ? turn : path.endsWith('/turns')
      ? { items: [{ ...turn, snapshot: undefined }], next_cursor: null } : path.endsWith(id) ? header : { items: [header], next_cursor: null };
    return route.fulfill({ json: value });
  });
  await page.goto(`/#history=${id}`);
  await expect(page.getByText('12.50', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText('12.50', { exact: true })).toBeVisible();
  expect(writes).toBe(0);
});

test('另存副本、独立重命名、删除来源与成果、显式重查创建新历史', async ({ page }) => {
  const { login, send } = await import('./helpers');
  let executions = 0;
  page.on('request', req => { if (req.method() === 'POST' && (req.url().endsWith('/turns') || req.url().endsWith('/requery'))) executions++; });
  await login(page);
  await send(page, '历史管理测试销售额');
  await expect(page.getByRole('table')).toBeVisible();
  const sourceUrl = page.url();
  await page.getByRole('button', { name: '另存成果', exact: true }).click();
  await page.getByLabel('成果名称').fill('固定成果甲');
  await page.getByRole('button', { name: '保存名称', exact: true }).click();
  await expect(page.getByText('已保存。', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '已保存成果', exact: true }).click();
  await page.getByRole('button', { name: '问数 · 固定成果甲', exact: true }).click();
  await expect(page.getByRole('heading', { name: '固定成果甲', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '重命名', exact: true }).click();
  await page.getByLabel('记录名称').fill('固定成果乙');
  await page.getByRole('button', { name: '保存名称', exact: true }).click();
  await expect(page.getByRole('heading', { name: '固定成果乙', exact: true })).toBeVisible();
  await page.goto(sourceUrl);
  await expect(page.getByRole('table')).toBeVisible();
  page.on('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: '删除历史', exact: true }).click();
  await expect(page.getByRole('table')).toHaveCount(0);
  await page.getByRole('button', { name: '已保存成果', exact: true }).click();
  await page.getByRole('button', { name: '问数 · 固定成果乙', exact: true }).click();
  await expect(page.getByRole('table')).toBeVisible();
  expect(executions).toBe(1);
  await page.getByRole('button', { name: '重新查询当前数据', exact: true }).click();
  await expect(page.getByRole('button', { name: '另存成果', exact: true })).toBeVisible();
  expect(page.url()).not.toBe(sourceUrl);
  expect(executions).toBe(2);
  await page.getByRole('button', { name: '已保存成果', exact: true }).click();
  await page.getByRole('button', { name: '问数 · 固定成果乙', exact: true }).click();
  await page.getByRole('button', { name: '删除成果', exact: true }).click();
  await page.getByRole('button', { name: '历史记录', exact: true }).click();
  await expect(page.getByRole('button', { name: /問数|问数 · 固定成果/ })).toBeVisible();
});

test('执行下一轮时可另存旧成功结果，且不丢失下一轮交付', async ({ page }) => {
  const { login, send } = await import('./helpers');
  await login(page); await send(page, '允许另存旧结果');
  await expect(page.getByRole('table')).toBeVisible();
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/histories/*/turns', async route => { await held; await route.continue(); });
  await send(page, '改成毛利');
  await expect(page.getByRole('status')).toBeVisible();
  await page.getByRole('button', { name: '另存成果', exact: true }).click();
  await page.getByLabel('成果名称').fill('执行期间副本');
  await page.getByRole('button', { name: '保存名称', exact: true }).click();
  await expect(page.getByText('已保存。', { exact: true })).toBeVisible();
  release();
  await expect(page.getByRole('table')).toHaveCount(2);
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeDisabled();
});
