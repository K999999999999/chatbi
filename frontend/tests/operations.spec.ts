import { test, expect } from '@playwright/test';
import { login, send } from './helpers';

test('服务拒绝追问时显示确定原因，恢复后沿用成功上下文', async ({ page }) => {
  await login(page);
  await send(page, '2025年2月净销售额');
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
  await send(page, '改成2025年3月');
  await expect(page.getByText('服务暂时不可用，请稍后重试', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '明确重试同一请求' })).toHaveCount(0);
  await expect(page.getByRole('table')).toHaveCount(1);
  expect(submissions).toHaveLength(1);
  rejected = false;
  await send(page, '改成2025年3月');
  await expect(page.getByRole('table')).toHaveCount(2);
  expect(submissions[1].expected_context_revision).toBe(1);
  expect(submissions[1].operation_id).not.toBe(submissions[0].operation_id);
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

test('administrator projection shows backup time and safe failure reason', async ({ page }) => {
  await page.route('**/api/v1/operations/status', route => route.fulfill({ json: {
    version: 1, status: 'ready', details: { dependencies: {}, model: { status: 'unknown' },
      backup: { overdue: true, last_success: '2026-10-01T12:00:00+00:00', failure_code: 'BACKUP_KEY_UNAVAILABLE' } },
  } }));
  await login(page);
  const status = page.getByLabel('运行状态');
  await status.locator('summary').click();
  await expect(status).toContainText('已超过24小时');
  await expect(status).toContainText('最近成功备份：');
  await expect(status).toContainText('备份密钥未初始化或不可用');
});

test('unrecognized backup error and invalid timestamp are not displayed', async ({ page }) => {
  await page.route('**/api/v1/operations/status', route => route.fulfill({ json: {
    version: 1, status: 'ready', details: { dependencies: {}, model: { status: 'unknown' },
      backup: { overdue: true, last_success: 'private-password', failure_code: 'private-password' } },
  } }));
  await login(page);
  const status = page.getByLabel('运行状态');
  await status.locator('summary').click();
  await expect(status).toContainText('尚无成功备份证据');
  await expect(status).not.toContainText('private-password');
});
