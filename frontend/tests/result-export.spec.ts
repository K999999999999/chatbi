import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('成功问数轮次通过浏览器下载 XLSX 快照', async ({ page }) => {
  const exportBodies: Record<string, unknown>[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/v1/result-exports')) {
      exportBodies.push(request.postDataJSON());
    }
  });
  await page.goto('/');
  await page.getByLabel('账号', { exact: true }).fill('analyst');
  await page.getByLabel('密码', { exact: true }).fill('test-password-123');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
  await page.getByRole('button', { name: '问数 · 浏览器导出验收历史', exact: true }).click();
  await expect(page.getByRole('table')).toBeVisible();
  const downloadReady = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 XLSX' }).click();
  const download = await downloadReady;
  expect(download.suggestedFilename()).toMatch(/^chatbi-query-[0-9a-f-]+\.xlsx$/);
  const bytes = await readFile(await download.path());
  expect(bytes.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 0x03, 0x04]));
  expect(bytes.length).toBeGreaterThan(1000);
  if (process.env.CHATBI_RESULT_EXPORT_CAPTURE_DIR) {
    await download.saveAs(`${process.env.CHATBI_RESULT_EXPORT_CAPTURE_DIR}/history.xlsx`);
  }
  expect(exportBodies[0]).toEqual({
    source: {
      kind: 'history_turn',
      history_id: expect.any(String),
      turn_id: expect.any(String),
    },
    format: 'xlsx',
  });

  await page.getByRole('button', { name: '另存成果' }).click();
  await page.getByLabel('成果名称').fill('浏览器导出成果');
  await page.getByRole('button', { name: '保存名称' }).click();
  await page.getByRole('button', { name: '已保存成果', exact: true }).click();
  const savedResult = page.getByRole('button', { name: '问数 · 浏览器导出成果', exact: true });
  await expect(savedResult).toBeVisible();
  await savedResult.click();
  const savedDownloadReady = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 XLSX', exact: true }).click();
  const savedDownload = await savedDownloadReady;
  const savedBytes = await readFile(await savedDownload.path());
  expect(savedBytes.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 0x03, 0x04]));
  expect(savedBytes.length).toBeGreaterThan(1000);
  if (process.env.CHATBI_RESULT_EXPORT_CAPTURE_DIR) {
    await savedDownload.saveAs(`${process.env.CHATBI_RESULT_EXPORT_CAPTURE_DIR}/saved-result.xlsx`);
  }
  expect(exportBodies[1]).toEqual({
    source: {
      kind: 'saved_result',
      saved_result_id: expect.any(String),
    },
    format: 'xlsx',
  });
});
