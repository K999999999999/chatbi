import { expect, type Page } from '@playwright/test';

export function isFinalExecutionResponse(response: { url(): string; request(): { method(): string } }): boolean {
  const path = new URL(response.url()).pathname;
  return response.request().method() === 'GET' && /^\/api\/v1\/executions\/[0-9a-f-]{36}$/.test(path);
}

export async function mockFinalExecution(page: Page, snapshot: unknown | ((current: unknown, call: number) => unknown)) {
  let calls = 0;
  await page.route('**/api/v1/executions/*', async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET' || path.endsWith('/events') || path.includes('/by-operation/')) return route.continue();
    const response = await route.fetch(); const body = await response.json();
    if (body.turn?.snapshot !== undefined) {
      calls += 1;
      body.turn.snapshot = typeof snapshot === 'function' ? snapshot(body.turn.snapshot, calls) : snapshot;
    }
    await route.fulfill({ response, json: body });
  });
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
