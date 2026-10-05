import { test, expect } from '@playwright/test';
import { login, send, mockFinalExecution } from './helpers';

test('logout failure stays explicit across refresh and clears private records', async ({ page }) => {
  await login(page);
  await send(page, '私有查询问题');
  await expect(page.getByRole('table')).toBeVisible();
  await page.route('**/auth/browser/logout', route => route.abort('failed'));
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByRole('button', { name: '重试退出' })).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('button', { name: '重试退出' })).toBeVisible();
  await expect(page.getByRole('button', { name: '退出登录', exact: true })).toHaveCount(0);
  await page.unroute('**/auth/browser/logout');
  await page.getByRole('button', { name: '重试退出' }).click();
  await expect(page.getByText('已退出登录。', { exact: true })).toBeVisible();
});

test('expired query session clears records and stale data cannot reappear', async ({ page }) => {
  await login(page);
  await send(page, '私有查询问题');
  await expect(page.getByRole('table')).toBeVisible();
  await page.route('**/api/v1/histories/*/executions', route => route.fulfill({ status: 401,
    json: { request_id: 'test', error_code: 'AUTHENTICATION_REQUIRED', error_message: '会话已失效' } }));
  await send(page, '追问');
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  await expect(page.getByText('私有查询问题', { exact: true })).toHaveCount(0);
});

test('account change in another tab clears private state without automatic replay', async ({ page, context }) => {
  await login(page);
  await send(page, '第一个账号的私有问题');
  await expect(page.getByRole('table')).toBeVisible();
  const other = await context.newPage();
  await other.goto('/');
  await expect(other.getByRole('button', { name: '退出登录' })).toBeVisible();
  await other.getByRole('button', { name: '退出登录' }).click();
  await login(other, 'other-user');
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  await expect(page.getByText('第一个账号的私有问题', { exact: true })).toHaveCount(0);
  await expect(other.getByLabel('问题')).toHaveValue('');
});

test('pending response cannot restore data after logout', async ({ page }) => {
  await login(page);
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  let arrived!: () => void;
  const received = new Promise<void>(resolve => { arrived = resolve; });
  await page.route('**/api/v1/histories/*/executions', async route => {
    const response = await route.fetch(); arrived(); await held;
    await route.fulfill({ response }).catch(() => {});
  });
  await send(page, '迟到的私有问题');
  await received;
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  release();
  await login(page, 'other-user');
  await expect(page.getByRole('table')).toHaveCount(0);
  await expect(page.getByText('迟到的私有问题', { exact: true })).toHaveCount(0);
});

test('SSE断连后只重连读取，不重复提交执行', async ({ page }) => {
  await login(page);
  let reads = 0; let submissions = 0;
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/executions')) submissions++; });
  await page.route('**/api/v1/executions/*/events', route => {
    reads++;
    return reads === 1 ? route.abort('failed') : route.continue();
  });
  await send(page, '完整问题');
  await expect(page.getByRole('table')).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
  expect(submissions).toBe(1);
});

test('SSE权限失效关闭观察并清除页面和历史列表中的私有内容', async ({ page }) => {
  await login(page);
  await send(page, '仅授权账号可见的历史问题');
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('button', { name: /问数 · 仅授权账号可见的历史问题/ })).toBeVisible();
  await page.getByLabel('搜索名称').fill('仅授权账号可见的历史问题');
  await page.getByRole('button', { name: '搜索', exact: true }).click();
  await expect(page.getByRole('button', { name: /问数 · 仅授权账号可见的历史问题/ })).toBeVisible();
  await page.route('**/api/v1/executions/*/events', route => {
    const executionId = new URL(route.request().url()).pathname.split('/').at(-2)!;
    const event = { version: 1, execution_id: executionId, sequence: 0, type: 'auth_lost', payload: {} };
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body: `id: 0\nevent: auth_lost\ndata: ${JSON.stringify(event)}\n\n` });
  });
  await send(page, '权限撤销后的下一条问题');
  await expect(page.getByRole('alert')).toContainText('当前身份已无权查看');
  await expect(page.getByRole('table')).toHaveCount(0);
  await expect(page.getByText('仅授权账号可见的历史问题', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /问数 · 仅授权账号可见的历史问题/ })).toHaveCount(0);
  await expect(page.getByLabel('搜索名称')).toHaveValue('');
});

test('browser CSRF and expected account reject before query', async ({ page }) => {
  await login(page);
  const results = await page.evaluate(async () => {
    const me = await (await fetch('/auth/browser/me')).json();
    const csrf = await fetch('/api/v1/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: '完整问题' }) });
    const account = await fetch('/api/v1/query', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-ChatBI-Request': 'browser', 'X-ChatBI-User-ID': String(me.user_id + 1) }, body: JSON.stringify({ question: '完整问题' }) });
    return [csrf.status, account.status];
  });
  expect(results).toEqual([403, 401]);
});

test('analysis text stays inert and displays authoritative contribution', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: '经营分析', exact: true }).click();
  await mockFinalExecution(page, (current: unknown) => {
    const body = current as Record<string, any>;
    body.report.title = '<img src=x onerror="window.hacked=true">';
    return body;
  });
  await send(page, '完整分析问题');
  await expect(page.getByRole('heading', { name: '<img src=x onerror="window.hacked=true">' })).toBeVisible();
  await expect(page.locator('.analysis-report img')).toHaveCount(0);
  await expect(page.getByRole('cell').filter({ hasText: '-20.00 元' })).toBeVisible();
  expect(await page.evaluate(() => 'hacked' in window)).toBe(false);
});
