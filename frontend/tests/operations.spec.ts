import { test, expect } from '@playwright/test';
import { login } from './helpers';

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
