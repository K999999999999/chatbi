import { test, expect } from '@playwright/test';
import { login, send } from './helpers';

test('manual modes retain separate drafts and query context', async ({ page }) => {
  const bodies: Record<string, unknown>[] = [];
  const paths: string[] = [];
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/executions')) { bodies.push(req.postDataJSON()); paths.push(new URL(req.url()).pathname); } });
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
  expect(paths[0]).toBe(paths[2]);
  expect(bodies[1].mode).toBe('analysis');
  expect(paths[1].split('/')[4]).not.toBe(paths[0].split('/')[4]);
  expect(bodies[1].question).toBeUndefined();
  expect(bodies[1].expected_record_revision).toBe(0);
  expect(bodies[2].expected_context_revision).toBe(1);
});

test('提交响应丢失后明确重试复用原编号且保留编辑草稿', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: '经营分析', exact: true }).click();
  const bodies: Record<string, unknown>[] = [];
  let calls = 0; const paths: string[] = [];
  await page.route('**/api/v1/histories/*/executions', async route => {
    bodies.push(route.request().postDataJSON()); paths.push(new URL(route.request().url()).pathname);
    if (++calls === 1) await route.abort('failed'); else await route.continue();
  });
  await send(page, '分析2025年2月相比2025年1月的毛利变化');
  await expect(page.getByText('受理结果暂未确认。可刷新该历史恢复观察，或明确重试同一请求。').first()).toBeVisible();
  await page.getByLabel('问题').fill('另一条完整问题');
  await page.getByRole('button', { name: '明确重试同一请求', exact: true }).click();
  await expect(page.getByRole('heading', { name: '两期经营分析报告' })).toBeVisible();
  expect(paths[1]).toBe(paths[0]);
  expect(bodies[1].operation_id).toBe(bodies[0].operation_id);
  await expect(page.getByLabel('问题')).toHaveValue('另一条完整问题');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('heading', { name: '两期经营分析报告' })).toHaveCount(1);
  expect(paths[2]).not.toBe(paths[0]);
});

test('controlled analysis rejection preserves query context and cannot silently recreate run', async ({ page }) => {
  await login(page);
  await send(page, '2025年2月净销售额');
  await expect(page.getByRole('table')).toBeVisible();
  await page.getByRole('button', { name: '经营分析', exact: true }).click();
  await page.route('**/api/v1/histories/*/executions', route => route.fulfill({ status: 422, json: { request_id: 'test', error_code: 'CANNOT_ANSWER', error_message: '任务已过期，无法恢复' } }));
  await send(page, '完整分析问题');
  await expect(page.getByText('任务已过期，无法恢复', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '恢复原分析' })).toHaveCount(0);
  await page.unroute('**/api/v1/histories/*/executions');
  await page.getByRole('button', { name: '问数', exact: true }).click();
  await send(page, '改成3月');
  await expect(page.getByRole('table')).toHaveCount(2);
});
