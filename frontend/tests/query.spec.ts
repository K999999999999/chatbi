import { test, expect, type Page } from '@playwright/test';

export async function login(page: Page) {
  await page.goto('/');
  await page.getByLabel('账号', { exact: true }).fill('analyst');
  await page.getByLabel('密码', { exact: true }).fill('test-password-123');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
}
async function send(page: Page, question: string) {
  await page.getByLabel('问题').fill(question);
  await page.getByRole('button', { name: '发送', exact: true }).click();
}

test('query table, successful context, failure recovery and refresh', async ({ page }) => {
  const bodies: Record<string, unknown>[] = [];
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/turns')) bodies.push(req.postDataJSON()); });
  await login(page);
  await send(page, '2025年2月净销售额');
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('cell', { name: '无数据', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '0', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '空字符串', exact: true })).toBeVisible();
  await page.getByText('查看经校验 SQL', { exact: true }).click();
  await expect(page.getByText('SELECT 100 AS sales', { exact: true })).toBeVisible();
  await send(page, '触发澄清');
  await expect(page.getByText('请明确指标口径', { exact: true })).toBeVisible();
  await send(page, '空结果');
  await expect(page.getByText('查询成功，没有匹配的数据。')).toBeVisible();
  expect(bodies[0]).toEqual({ question: '2025年2月净销售额', expected_context_revision: 0, operation_id: expect.any(String) });
  expect(bodies[1].expected_context_revision).toBe(1);
  expect(bodies[2].expected_context_revision).toBe(1);
  await page.reload();
  await expect(page.getByLabel('问题')).toBeVisible();
  await expect(page.getByText('查询成功，没有匹配的数据。')).toBeVisible();
  expect(bodies).toHaveLength(3);
});

test('disconnect requires new dialogue and never resends automatically', async ({ page }) => {
  await login(page);
  let count = 0;
  await page.route('**/api/v1/histories/*/turns', route => { count++; return route.abort('failed'); });
  await send(page, '2025年2月净销售额');
  await expect(page.getByText('结果未确认，请刷新历史；本请求不会自动重试。')).toBeVisible();
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeDisabled();
  expect(count).toBe(1);
  await page.getByRole('button', { name: '新建问数对话' }).click();
  await page.getByLabel('问题').fill('完整问题');
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeEnabled();
});

test('pending locks actions but preserves the next draft; truncation is explicit', async ({ page }) => {
  await login(page);
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/histories/*/turns', async route => { await held; await route.continue(); });
  await send(page, '截断结果');
  await expect(page.getByRole('status')).toHaveText('正在查询…');
  await page.getByLabel('问题').fill('下一条问题');
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: '新建问数对话' })).toBeDisabled();
  release();
  await expect(page.getByText(/结果已截断/)).toBeVisible();
  await expect(page.getByLabel('问题')).toHaveValue('下一条问题');
});

test('malformed successful response cannot become trusted query context', async ({ page }) => {
  await login(page);
  await page.route('**/api/v1/histories/*/turns', route => route.fulfill({ json: { conversation_id: 'bad', rows: [{}] } }));
  await send(page, '完整问题');
  await expect(page.getByText('结果未确认，请刷新历史；本请求不会自动重试。')).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
});

test('successful and controlled failed requests retain diagnostic ids', async ({ page }) => {
  await login(page);
  await send(page, '完整问题');
  await expect(page.getByRole('table')).toBeVisible();
  await page.getByText('查看请求信息').click();
  await expect(page.getByText(/请求编号：/)).toBeVisible();
  await expect(page.getByText(/链路编号：[0-9a-f]{32}/)).toBeVisible();
  await send(page, '触发澄清');
  await expect(page.getByText('请明确指标口径', { exact: true })).toBeVisible();
  await page.getByText('查看请求信息').last().click();
  await expect(page.getByText(/链路编号：[0-9a-f]{32}/)).toHaveCount(2);
});
