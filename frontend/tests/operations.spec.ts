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
