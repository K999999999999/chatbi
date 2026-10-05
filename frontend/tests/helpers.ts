import { expect, type Page, type Route } from '@playwright/test';
export async function queryResponse(route: Route, snapshot: unknown) {
  const response = await route.fetch(); const body = await response.json();
  body.turn.snapshot = snapshot;
  await route.fulfill({ response, json: body });
}
export async function login(page: Page, username = 'analyst', password = 'test-password-123') {
  await page.goto('/');
  await page.getByLabel('账号', { exact: true }).fill(username);
  await page.getByLabel('密码', { exact: true }).fill(password);
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
}
export async function send(page: Page, question: string) {
  await page.getByLabel('问题').fill(question);
  await page.getByRole('button', { name: '发送', exact: true }).click();
}
