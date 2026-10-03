import { test, expect } from '@playwright/test';
import { login, send } from './helpers';

test('manual modes retain separate drafts and query context', async ({ page }) => {
  const bodies: Record<string, unknown>[] = [];
  let firstContext = '';
  page.on('response', async response => { if (response.url().endsWith('/api/v1/query') && !firstContext && response.ok()) firstContext = (await response.json()).conversation_id; });
  page.on('request', req => { if (req.url().endsWith('/api/v1/query')) bodies.push(req.postDataJSON()); });
  await login(page);
  await send(page, '2025年2月净销售额');
  await expect(page.getByRole('table')).toBeVisible();
  await page.getByLabel('问题').fill('问数草稿');
  await page.getByRole('button', { name: '经营分析', exact: true }).click();
  await expect(page.getByLabel('问题')).toHaveValue('');
  await send(page, '分析2025年2月相比2025年1月的毛利变化');
  await expect(page.getByRole('heading', { name: '两期经营分析报告' })).toBeVisible();
  await page.getByText('查看查询任务证据').click();
  await expect(page.getByText('查看查询任务证据').locator('..').getByRole('table')).toBeVisible();
  await page.getByRole('button', { name: '问数', exact: true }).click();
  await expect(page.getByLabel('问题')).toHaveValue('问数草稿');
  await send(page, '改成3月');
  await expect(page.getByRole('table')).toHaveCount(2);
  expect(bodies[1].mode).toBe('analysis');
  expect(bodies[1].conversation_id).toBeUndefined();
  expect(bodies[1].analysis_run_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(bodies[2].conversation_id).toBe(firstContext);
  expect(bodies[2].conversation_id).toBeTruthy();
});

test('analysis recovery reuses original question and id despite changed draft', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: '经营分析', exact: true }).click();
  const bodies: Record<string, unknown>[] = [];
  let calls = 0;
  await page.route('**/api/v1/query', async route => {
    bodies.push(route.request().postDataJSON());
    if (++calls === 1) await route.abort('failed'); else await route.continue();
  });
  await send(page, '分析2025年2月相比2025年1月的毛利变化');
  await expect(page.getByText('分析结果未确认，可用原问题和原任务编号手动重试。')).toBeVisible();
  await page.getByLabel('问题').fill('另一条完整问题');
  await page.getByRole('button', { name: '重试原分析' }).click();
  await expect(page.getByRole('heading', { name: '两期经营分析报告' })).toBeVisible();
  expect(bodies[1]).toEqual(bodies[0]);
  await expect(page.getByLabel('问题')).toHaveValue('另一条完整问题');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('heading', { name: '两期经营分析报告' })).toHaveCount(2);
  expect(bodies[2].analysis_run_id).not.toBe(bodies[0].analysis_run_id);
});

test('controlled analysis rejection preserves query context and cannot silently recreate run', async ({ page }) => {
  await login(page);
  await send(page, '2025年2月净销售额');
  await expect(page.getByRole('table')).toBeVisible();
  await page.getByRole('button', { name: '经营分析', exact: true }).click();
  await page.route('**/api/v1/query', route => route.fulfill({ status: 422, json: { request_id: 'test', error_code: 'CANNOT_ANSWER', error_message: '任务已过期，无法恢复' } }));
  await send(page, '完整分析问题');
  await expect(page.getByText('任务已过期，无法恢复', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '重试原分析' })).toHaveCount(0);
  await page.unroute('**/api/v1/query');
  await page.getByRole('button', { name: '问数', exact: true }).click();
  await send(page, '改成3月');
  await expect(page.getByRole('table')).toHaveCount(2);
});
