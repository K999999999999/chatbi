import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { login, send } from './helpers';
import { queryResult } from '../src/results';
import { analysisResult } from '../src/Analysis';
import { buildChartPlans } from '../src/chartPlan';

test('源码挂载实际触发 Python 重载与 Vite 热更新', async ({ page }) => {
  const backend = '/workspace/backend-src/query_api/app.py';
  const css = '/workspace/frontend/src/style.css';
  const originalBackend = readFileSync(backend, 'utf8');
  const originalCss = readFileSync(css, 'utf8');
  const marker = 'return {"status": "ok"}';
  expect(originalBackend.split(marker).length).toBe(2);
  const changedBackend = originalBackend.replace(marker, 'return {"status": "hot-reload-check"}');
  const changedCss = `${originalCss}\nbody { --chatbi-hot-check: 1; }\n`;
  await page.goto('/');
  try {
    writeFileSync(backend, changedBackend);
    await expect.poll(async () => {
      try { return (await (await page.request.get('/health')).json()).status; } catch { return 'restarting'; }
    }, { timeout: 60000 }).toBe('hot-reload-check');
    writeFileSync(css, changedCss);
    await expect.poll(() => page.evaluate(() => getComputedStyle(document.body).getPropertyValue('--chatbi-hot-check').trim()),
      { timeout: 30000 }).toBe('1');
    writeFileSync('/reports/hot-reload.json', JSON.stringify({
      commit: process.env.CHATBI_CONTAINER_COMMIT, experiment_dirty: true,
      python_reload: true, vite_hmr: true,
    }));
  } finally {
    let concurrentChange = false;
    if (readFileSync(backend, 'utf8') === changedBackend) writeFileSync(backend, originalBackend);
    else concurrentChange = true;
    const currentCss = readFileSync(css, 'utf8');
    if (currentCss === changedCss) writeFileSync(css, originalCss);
    else if (currentCss !== originalCss) concurrentChange = true;
    if (concurrentChange) throw new Error('源码被并发修改，已恢复可安全恢复的文件并保留现场');
  }
  await expect.poll(async () => {
    try { return (await (await page.request.get('/health')).json()).status; } catch { return 'restarting'; }
  }, { timeout: 60000 }).toBe('ok');
});

test('实际 Compose 网页登录 → 真实问数 → 同一对话追问', async ({ page, browser }) => {
  const reference = JSON.parse(process.env.CHATBI_CONTAINER_REFERENCE!);
  const evidence: Record<string, unknown> = {
    commit: process.env.CHATBI_CONTAINER_COMMIT, git_dirty: process.env.CHATBI_CONTAINER_GIT_DIRTY === 'true',
    username: process.env.CHATBI_REAL_E2E_USERNAME, reference,
    at: new Date().toISOString(), browser: browser.version(), target: 'compose-vite-api',
  };
  try {
    await login(page, process.env.CHATBI_REAL_E2E_USERNAME!, process.env.CHATBI_REAL_E2E_PASSWORD!);
    const firstResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/query'), { timeout: 240000 });
    await send(page, '2025年2月已完成订单的人民币净销售额是多少？');
    const firstHttp = await firstResponse;
    const firstPayload = await firstHttp.json();
    evidence.first_http_status = firstHttp.status();
    evidence.first_error_code = firstPayload.error_code;
    const first = queryResult(firstPayload);
    expect(first.rows.length).toBe(1);
    expect(Number(first.rows[0][0])).toBe(Number(reference.net_sales['2']));
    await expect(page.getByRole('table')).toBeVisible();
    const secondResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/query'), { timeout: 240000 });
    await send(page, '改成2025年3月');
    const second = queryResult(await (await secondResponse).json());
    expect(second.conversation_id).toBe(first.conversation_id);
    expect(Number(second.rows[0][0])).toBe(Number(reference.net_sales['3']));
    evidence.query = { value: first.rows[0][0], conversation_id: first.conversation_id };
    evidence.followup = { value: second.rows[0][0], conversation_id: second.conversation_id };
    expect(first.result_metadata?.columns[0].semantic_name).toBe('人民币净销售额');
    expect(first.result_metadata?.columns[0].unit?.key).toBe('CNY');
    expect(first.result_metadata?.scope.time?.start).toBe('2025-02-01');
    expect(second.result_metadata?.scope.time?.start).toBe('2025-03-01');
    await page.getByRole('button', { name: '新建问数对话' }).click();
    const trendResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/query'), { timeout: 240000 });
    await send(page, '按月份列出2025年已完成订单的人民币净销售额、人民币毛利和毛利率。');
    const trend = queryResult(await (await trendResponse).json());
    const trendMetadata = trend.result_metadata!;
    expect(trendMetadata.scope.grouping).toHaveLength(1);
    expect(trendMetadata.time_axis?.granularity).toBe('month');
    const metricNames = ['人民币净销售额', '人民币毛利', '毛利率'];
    expect(trend.rows.length).toBe(Object.keys(reference.monthly).length);
    trend.rows.forEach((row, index) => {
      const expected = reference.monthly[trendMetadata.time_axis!.keys[index]];
      expect(expected).toBeTruthy();
      metricNames.forEach((name, metricIndex) => {
        const column = trendMetadata.columns.find(c => c.semantic_name === name && c.certified)!;
        expect(column).toBeTruthy();
        expect(Number(row[column.index])).toBeCloseTo(Number(expected[metricIndex]), 8);
      });
    });
    const trendPlans = buildChartPlans(trend);
    expect(trendPlans.plans).toHaveLength(2);
    expect(trendPlans.plans.find(p => p.id === 'CNY')?.series).toHaveLength(2);
    await expect(page.locator('.chart-canvas svg')).toHaveCount(2);
    await expect(page.getByRole('table')).toBeVisible();
    await page.getByLabel('图表类型').first().selectOption('bar');
    await expect(page.locator('[data-chart-kind="bar"] svg')).toHaveCount(1);
    evidence.monthly_mixed_units = { rows: trend.rows.length, reference_matches: true, money_series: 2, chart_units: trendPlans.plans.map(p => p.id), metadata_status: trendMetadata.status };
    await page.getByRole('button', { name: '新建问数对话' }).click();
    const categoryResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/query'), { timeout: 240000 });
    await send(page, '按产品线列出2025年已完成订单的人民币净销售额和人民币销售成本。');
    const category = queryResult(await (await categoryResponse).json());
    const categoryMeta = category.result_metadata!;
    const dimension = categoryMeta.columns.find(c => c.semantic_name === '产品线' && c.certified)!;
    expect(dimension).toBeTruthy();
    expect(category.rows.length).toBe(Object.keys(reference.categories).length);
    category.rows.forEach(row => {
      const expected = reference.categories[String(row[dimension.index])];
      expect(expected).toBeTruthy();
      ['人民币净销售额', '人民币销售成本'].forEach((name, metricIndex) => {
        const column = categoryMeta.columns.find(c => c.semantic_name === name && c.certified)!;
        expect(column).toBeTruthy();
        expect(Number(row[column.index])).toBeCloseTo(Number(expected[metricIndex]), 8);
      });
    });
    expect(buildChartPlans(category).plans[0].series).toHaveLength(2);
    await expect(page.locator('.chart-canvas svg')).toHaveCount(1);
    evidence.category_same_unit = { rows: category.rows.length, reference_matches: true, series: 2, metadata_status: categoryMeta.status };
    evidence.step = 'analysis-request';
    await page.getByRole('button', { name: '经营分析', exact: true }).click();
    const analysisResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/query'), { timeout: 600000 });
    await send(page, '分析2025年3月相比2025年2月的人民币毛利变化及产品因素贡献。');
    const analysisHttp = await analysisResponse;
    evidence.analysis_http_status = analysisHttp.status();
    evidence.step = 'analysis-parse';
    const analysis = analysisResult(await analysisHttp.json(), analysisHttp.request().postDataJSON().analysis_run_id);
    evidence.step = 'analysis-reference';
    const { reconciliation_passed: _reconciled, ...expectedAttribution } = reference.attribution;
    expect(analysis.report.attribution).toEqual(expect.objectContaining(expectedAttribution));
    expect(analysis.task_results).toHaveLength(4);
    expect(analysis.task_results.every(t => t.status === 'completed' && !t.truncated)).toBe(true);
    evidence.step = 'analysis-render';
    await expect(page.locator('.attribution .chart-canvas svg')).toHaveCount(2);
    await expect(page.locator('.attribution table')).toBeVisible();
    await page.getByText('查看查询任务证据').click();
    await expect(page.getByText('查看查询任务证据').locator('..').getByRole('table')).toHaveCount(4);
    evidence.analysis = { reference_matches: true, direction: analysis.report.attribution!.direction, tasks_completed: 4, task_metadata: analysis.task_results.map(t => t.result_metadata?.status ?? 'absent'), product_factor_charts: true };
    evidence.step = 'complete';
    evidence.status = 'passed';
    await page.getByRole('button', { name: '退出登录' }).click();
    await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  } catch (error) {
    evidence.status = 'failed'; evidence.error_type = (error as Error).name;
    evidence.error_locations = (error as Error).stack?.match(/container-real\.spec\.ts:\d+:\d+/g) ?? [];
    throw new Error('真实容器业务验收失败，见私有报告的步骤与安全定位。');
  } finally {
    writeFileSync('/reports/browser.json', JSON.stringify(evidence, null, 2));
  }
});
