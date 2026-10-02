import { test, expect } from '@playwright/test';
import { login, send } from './helpers';

test('Vite same-origin proxy supports browser login and both modes', async ({ page }) => {
  await login(page);
  await send(page, '2025年2月净销售额');
  await expect(page.getByRole('table')).toBeVisible();
  await page.getByRole('button', { name: '经营分析', exact: true }).click();
  await send(page, '分析2025年2月相比2025年1月毛利变化');
  await expect(page.getByRole('heading', { name: '两期经营分析报告' })).toBeVisible();
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
});
