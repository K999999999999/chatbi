import { test, expect, type Page } from '@playwright/test';

async function login(page: Page, name = 'analyst', password = 'test-password-123') {
  await page.goto('/');
  await page.getByLabel('账号', { exact: true }).fill(name);
  await page.getByLabel('密码', { exact: true }).fill(password);
  await page.getByRole('button', { name: '登录', exact: true }).click();
}

test('login refresh retains identity and logout removes it', async ({ page }) => {
  await login(page);
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
});

test('first password change requires new login', async ({ page }) => {
  await login(page, 'new-user');
  await expect(page.getByRole('heading', { name: '首次登录，请修改密码' })).toBeVisible();
  await page.getByLabel('当前密码').fill('test-password-123');
  await page.getByLabel('新密码').fill('changed-password-123');
  await page.getByRole('button', { name: '修改密码', exact: true }).click();
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  await page.getByLabel('密码', { exact: true }).fill('changed-password-123');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
});
