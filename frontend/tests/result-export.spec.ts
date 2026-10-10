import { test, expect, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

async function captureDownloadName(page: Page) {
  await page.evaluate(() => {
    document.addEventListener('click', event => {
      const anchor = event.target;
      if (anchor instanceof HTMLAnchorElement && anchor.hasAttribute('download')) {
        document.documentElement.dataset.downloadName = anchor.download;
      }
    }, true);
  });
}

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
  await captureDownloadName(page);
  const downloadReady = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 XLSX' }).click();
  const download = await downloadReady;
  await expect(page.locator('html')).toHaveAttribute('data-download-name', /^浏览器导出验收历史-查询结果-\d{8}T\d{6}Z\.xlsx$/);
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

test('成功查询图表按当前选择触发浏览器 PNG 下载', async ({ page }) => {
  const exportBodies: Record<string, unknown>[] = [];
  await page.route('**/api/v1/result-exports', async route => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    exportBodies.push(body);
    const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');
    const filename = encodeURIComponent('浏览器导出验收历史-图表-20261006T000000Z.png');
    await route.fulfill({ status: 200, contentType: 'image/png',
      headers: { 'Content-Disposition': `attachment; filename="chart.png"; filename*=UTF-8''${filename}` }, body: png });
  });
  await page.goto('/');
  await page.getByLabel('账号', { exact: true }).fill('analyst');
  await page.getByLabel('密码', { exact: true }).fill('test-password-123');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await page.getByRole('button', { name: '问数 · 浏览器导出验收历史', exact: true }).click();
  const pngButton = page.getByRole('button', { name: /下载.*PNG/ }).first();
  await expect(pngButton).toBeVisible();
  await captureDownloadName(page);
  const downloadReady = page.waitForEvent('download');
  await pngButton.click();
  const download = await downloadReady;
  await expect(page.locator('html')).toHaveAttribute('data-download-name', /^浏览器导出验收历史-图表-\d{8}T\d{6}Z\.png$/);
  const bytes = await readFile(await download.path());
  expect(bytes.subarray(0, 8)).toEqual(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  expect(exportBodies).toHaveLength(1);
  const body = exportBodies[0];
  expect(body.source).toEqual({ kind: 'history_turn', history_id: expect.any(String), turn_id: expect.any(String) });
  expect(body.format).toBe('png');
  expect(body.chart_type).toBe('bar');
  expect(body.chart_id).toBe('CNY');
});
