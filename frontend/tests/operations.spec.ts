import { test, expect } from '@playwright/test';
import {
  isExecutionSubmissionRejection,
  isFinalExecutionResponse,
  login,
  send,
  waitForOperationsReady,
} from './helpers';

test('服务拒绝追问时显示确定原因，恢复后沿用成功上下文', async ({ page }) => {
  await login(page);
  const firstQuery = page.waitForResponse(isFinalExecutionResponse);
  await send(page, '2025年2月净销售额');
  await firstQuery;
  await expect(page.getByRole('table')).toHaveCount(1);
  const submissions: Record<string, unknown>[] = [];
  let rejected = true;
  await page.route('**/api/v1/histories/*/executions', route => {
    submissions.push(route.request().postDataJSON());
    return rejected ? route.fulfill({ status: 503, json: {
      request_id: 'readiness-rejected', error_code: 'SERVICE_NOT_READY',
      error_message: '服务暂时不可用，请稍后重试',
    } }) : route.continue();
  });
  const rejection = page.waitForResponse(isExecutionSubmissionRejection);
  await send(page, '改成2025年3月');
  expect((await rejection).status()).toBe(503);
  await expect(page.getByText('服务暂时不可用，请稍后重试', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '明确重试同一请求' })).toHaveCount(0);
  await expect(page.getByRole('table')).toHaveCount(1);
  expect(submissions).toHaveLength(1);
  rejected = false;
  const recoveredQuery = page.waitForResponse(isFinalExecutionResponse);
  await send(page, '改成2025年3月');
  await recoveredQuery;
  await expect(page.getByRole('table')).toHaveCount(2);
  expect(submissions[1].expected_context_revision).toBe(1);
  expect(submissions[1].operation_id).not.toBe(submissions[0].operation_id);
});

test('容器验收轮询公开就绪状态，并在服务恢复后才继续', async ({ page }) => {
  await login(page);
  const statuses = ['unknown', 'not_ready', 'ready'] as const;
  let attempts = 0;
  await page.route('**/api/v1/operations/status', route => {
    const status = statuses[Math.min(attempts, statuses.length - 1)];
    attempts += 1;
    return route.fulfill({
      status: status === 'ready' ? 200 : 503,
      headers: { 'Cache-Control': 'no-store' },
      json: { version: 1, status, checked_at: null, query_available: status === 'ready', message: '' },
    });
  });

  const readiness = await waitForOperationsReady(page, { timeoutMs: 2000, intervalMs: 10 });

  expect(readiness.status).toBe('ready');
  expect(readiness.attempts).toBe(3);
  expect(attempts).toBe(3);
});

test('就绪状态持续失败时验收等待在边界内退出并记录安全状态', async ({ page }) => {
  await login(page);
  await page.route('**/api/v1/operations/status', route => route.fulfill({
    status: 503,
    headers: { 'Cache-Control': 'no-store' },
    json: { version: 1, status: 'not_ready', checked_at: null, query_available: false, message: '' },
  }));

  await expect(waitForOperationsReady(page, { timeoutMs: 100, intervalMs: 10 }))
    .rejects.toThrow('最近状态：not_ready');
});

test('服务拒绝经营分析时显示确定原因，恢复后可以重新提交', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: '经营分析', exact: true }).click();
  await page.route('**/api/v1/histories/*/executions', route => route.fulfill({ status: 503, json: {
    request_id: 'readiness-rejected', error_code: 'SERVICE_NOT_READY',
    error_message: '服务暂时不可用，请稍后重试',
  } }));
  await send(page, '分析2025年2月相比2025年1月的毛利变化');
  await expect(page.getByText('服务暂时不可用，请稍后重试', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '明确重试同一请求' })).toHaveCount(0);
  await page.unroute('**/api/v1/histories/*/executions');
  await send(page, '分析2025年2月相比2025年1月的毛利变化');
  await expect(page.getByRole('heading', { name: '两期经营分析报告' })).toBeVisible();
});

test('服务拒绝重新查询时保留原结果并显示确定原因', async ({ page }) => {
  await login(page);
  await send(page, '2025年2月净销售额');
  await expect(page.getByRole('table')).toHaveCount(1);
  await page.route('**/api/v1/histories/*/requery-executions', route => route.fulfill({ status: 503, json: {
    request_id: 'readiness-rejected', error_code: 'SERVICE_NOT_READY',
    error_message: '服务暂时不可用，请稍后重试',
  } }));
  await page.getByRole('button', { name: '重新查询当前数据', exact: true }).click();
  await expect(page.getByText('服务暂时不可用，请稍后重试', { exact: true })).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(1);
});

test('未知503仍恢复已持久受理的请求，不重复提交', async ({ page }) => {
  await login(page);
  let submissions = 0;
  await page.route('**/api/v1/histories/*/executions', async route => {
    submissions += 1;
    await route.fetch();
    await route.fulfill({ status: 503, json: {
      request_id: 'response-unconfirmed', error_code: 'HISTORY_STORAGE_UNAVAILABLE',
      error_message: '历史存储暂时不可用',
    } });
  });
  await send(page, '2025年2月净销售额');
  await expect(page.getByRole('table')).toHaveCount(1);
  expect(submissions).toBe(1);
  await expect(page.getByRole('button', { name: '明确重试同一请求' })).toHaveCount(0);
});

test('ordinary account sees outage and recovery without detailed diagnostics', async ({ page }) => {
  let status = 'not_ready';
  await page.route('**/api/v1/operations/status', route => route.fulfill({ json: {
    version: 1, status, checked_at: null, query_available: status === 'ready', message: '',
  } }));
  await login(page);
  await expect(page.getByLabel('运行状态')).toContainText('服务暂时不可用');
  await expect(page.getByLabel('运行状态').locator('details')).toHaveCount(0);
  status = 'ready';
  await page.reload();
  await expect(page.getByLabel('运行状态')).not.toContainText('服务暂时不可用');
});

test('expired background status returns user to login', async ({ page }) => {
  await page.route('**/api/v1/operations/status', route => route.fulfill({ status: 401,
    json: { detail: '登录已失效，请重新登录' } }));
  await page.goto('/');
  await page.getByLabel('账号', { exact: true }).fill('analyst');
  await page.getByLabel('密码', { exact: true }).fill('test-password-123');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  await expect(page.getByText('登录已失效，请重新登录。')).toBeVisible();
});

test('administrator sees application diagnostics without backup operations', async ({ page }) => {
  await page.route('**/api/v1/operations/status', route => route.fulfill({ json: {
    version: 1, status: 'ready', details: {
      dependencies: { control_database: 'ready', business_database: 'ready', qdrant: 'ready', assets: 'ready' },
      model: { status: 'success' }, capacity: { business: { active: 1, max_total: 4 }, export: { active: 0, max_total: 2 } },
    },
  } }));
  await login(page);
  const status = page.getByLabel('运行状态');
  await status.locator('summary').click();
  await expect(status).toContainText('检索服务：可用');
  await expect(status).toContainText('最近调用成功');
  await expect(status).toContainText('业务执行：1 / 4');
  await expect(status).not.toContainText('备份');
});
