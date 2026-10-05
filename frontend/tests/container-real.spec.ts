import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { login, send } from './helpers';
import { querySnapshot } from '../src/results';
import { analysisResult } from '../src/Analysis';
import { buildChartPlans } from '../src/chartPlan';

test('源码挂载实际触发 Python 重载与 Vite 热更新', async ({ page }) => {
  test.skip(process.env.CHATBI_CONTAINER_RESTART_PHASE === '1');
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
  test.skip(process.env.CHATBI_CONTAINER_RESTART_PHASE === '1');
  const reference = JSON.parse(process.env.CHATBI_CONTAINER_REFERENCE!);
  const evidence: Record<string, unknown> = {
    commit: process.env.CHATBI_CONTAINER_COMMIT, git_dirty: process.env.CHATBI_CONTAINER_GIT_DIRTY === 'true',
    username: process.env.CHATBI_REAL_E2E_USERNAME, reference,
    at: new Date().toISOString(), browser: browser.version(), target: 'compose-vite-api',
  };
  try {
    await login(page, process.env.CHATBI_REAL_E2E_USERNAME!, process.env.CHATBI_REAL_E2E_PASSWORD!);
    const firstResponse = page.waitForResponse(r => r.request().method() === 'POST' && /\/(turns|resume)$/.test(new URL(r.url()).pathname), { timeout: 240000 });
    await send(page, '2025年2月已完成订单的人民币净销售额是多少？');
    const firstHttp = await firstResponse;
    const firstPayload = await firstHttp.json();
    evidence.first_http_status = firstHttp.status();
    evidence.first_error_code = firstPayload.error_code;
    const first = querySnapshot(firstPayload.turn.snapshot);
    expect(first.rows.length).toBe(1);
    expect(Number(first.rows[0][0])).toBe(Number(reference.net_sales['2']));
    await expect(page.getByRole('table')).toBeVisible();
    const secondResponse = page.waitForResponse(r => r.request().method() === 'POST' && /\/(turns|resume)$/.test(new URL(r.url()).pathname), { timeout: 240000 });
    await send(page, '改成2025年3月');
    const secondHttp = await secondResponse;
    const secondPayload = await secondHttp.json();
    evidence.followup_http_status = secondHttp.status();
    evidence.followup_error_code = secondPayload.error_code;
    if (!secondPayload.turn?.snapshot) throw new Error('follow-up did not commit a successful snapshot');
    const second = querySnapshot(secondPayload.turn.snapshot);
    expect(secondPayload.history.id).toBe(firstPayload.history.id);
    expect(Number(second.rows[0][0])).toBe(Number(reference.net_sales['3']));
    evidence.query = { value: first.rows[0][0], history_id: firstPayload.history.id };
    evidence.followup = { value: second.rows[0][0], history_id: secondPayload.history.id };
    expect(first.result_metadata?.columns[0].semantic_name).toBe('人民币净销售额');
    expect(first.result_metadata?.columns[0].unit?.key).toBe('CNY');
    expect(first.result_metadata?.scope.time?.start).toBe('2025-02-01');
    expect(second.result_metadata?.scope.time?.start).toBe('2025-03-01');
    await page.getByRole('button', { name: '新建问数对话' }).click();
    const trendResponse = page.waitForResponse(r => r.request().method() === 'POST' && /\/(turns|resume)$/.test(new URL(r.url()).pathname), { timeout: 240000 });
    await send(page, '按月份列出2025年已完成订单的人民币净销售额、人民币毛利和毛利率。');
    evidence.step = 'monthly-query';
    const trendHttp = await trendResponse;
    const trendPayload = await trendHttp.json();
    evidence.monthly_http_status = trendHttp.status();
    evidence.monthly_error_code = trendPayload.error_code ?? trendPayload.turn?.error_code;
    if (!trendPayload.turn?.snapshot) throw new Error('monthly query did not commit a successful snapshot');
    const trend = querySnapshot(trendPayload.turn.snapshot);
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
    const categoryResponse = page.waitForResponse(r => r.request().method() === 'POST' && /\/(turns|resume)$/.test(new URL(r.url()).pathname), { timeout: 240000 });
    await send(page, '按产品线列出2025年已完成订单的人民币净销售额和人民币销售成本。');
    const categoryPayload = await (await categoryResponse).json();
    const category = querySnapshot(categoryPayload.turn.snapshot);
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
    const analysisResponse = page.waitForResponse(r => r.request().method() === 'POST' && /\/(turns|resume)$/.test(new URL(r.url()).pathname), { timeout: 600000 });
    await send(page, '分析2025年3月相比2025年2月的人民币毛利变化及产品因素贡献。');
    const analysisHttp = await analysisResponse;
    evidence.analysis_http_status = analysisHttp.status();
    evidence.step = 'analysis-parse';
    const analysisPayload = await analysisHttp.json();
    const analysis = analysisResult(analysisPayload.turn.snapshot, analysisPayload.history.analysis_run_id);
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
    evidence.step = 'r3-history';
    const analysisUrl = page.url();
    await page.reload(); await expect(page.locator('.analysis-report h2')).toBeVisible();
    await page.getByRole('button', { name: '另存成果', exact: true }).click();
    await page.getByLabel('成果名称').fill('R3固定分析报告');
    await page.getByRole('button', { name: '保存名称', exact: true }).click();
    await expect(page.getByText('已保存。', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '问数', exact: true }).click();
    evidence.step = 'history-search-query';
    await page.getByLabel('记录类型').selectOption('query');
    await page.getByLabel('搜索名称').fill('按产品线列出2025年已完成订单');
    await page.getByRole('button', { name: '搜索', exact: true }).click();
    await page.getByRole('button', { name: /问数 · 按产品线列出2025年已完成订单/ }).click();
    await expect(page.getByRole('table')).toBeVisible();
    await page.getByLabel('搜索名称').fill('');
    await page.getByRole('button', { name: '搜索', exact: true }).click();
    evidence.step = 'save-query-result';
    await page.getByRole('button', { name: '另存成果', exact: true }).click();
    await page.getByLabel('成果名称').fill('R3固定分类成果');
    await page.getByRole('button', { name: '保存名称', exact: true }).click();
    await expect(page.getByText('已保存。', { exact: true })).toBeVisible();
    page.on('dialog', dialog => dialog.accept());
    evidence.step = 'delete-source-history';
    await page.getByRole('button', { name: '删除历史', exact: true }).click();
    await expect(page.getByRole('table')).toHaveCount(0);
    await page.getByRole('button', { name: '已保存成果', exact: true }).click();
    evidence.step = 'open-saved-copy';
    await page.getByRole('button', { name: '问数 · R3固定分类成果', exact: true }).click();
    await expect(page.getByRole('table')).toBeVisible();
    const savedUrl = page.url();
    await page.getByRole('button', { name: '新建问数对话', exact: true }).click();
    evidence.step = 'top-n-query';
    const rankedResponse = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/turns'), { timeout: 240000 });
    await send(page, '2025年3月按人民币净销售额从高到低列出前3个产品。');
    const rankedPayload = await (await rankedResponse).json(); const ranked = querySnapshot(rankedPayload.turn.snapshot);
    expect(ranked.rows.map(row => [String(row[0]), Number(row[1])])).toEqual(reference.top_products.map((row: unknown[]) => [String(row[0]), Number(row[1])]));
    evidence.restart_inputs = { ranked_history_id: rankedPayload.history.id, analysis_history_id: analysisPayload.history.id, analysis_run_id: analysisPayload.history.analysis_run_id, saved_url: savedUrl, analysis_url: analysisUrl };
    evidence.r3_before_restart = { saved_independent: true, refresh_analysis: true, top_n_reference: true };
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


test('停止重启后读取长期快照、重登录、续聊与显式重查', async ({ page }) => {
  test.skip(process.env.CHATBI_CONTAINER_RESTART_PHASE !== '1');
  const evidence = JSON.parse(readFileSync('/reports/browser.json', 'utf8'));
  const input = evidence.restart_inputs; const reference = evidence.reference;
  try {
    await login(page, process.env.CHATBI_REAL_E2E_USERNAME!, process.env.CHATBI_REAL_E2E_PASSWORD!);
    await expect(page.getByRole('table')).toHaveCount(0);
    await page.goto('/#history=' + input.ranked_history_id);
    await expect(page.getByRole('table')).toBeVisible();
    const continued = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/turns'), { timeout: 240000 });
    await send(page, '只看前2个产品');
    const body = await (await continued).json(); const result = querySnapshot(body.turn.snapshot);
    expect(body.history.id).toBe(input.ranked_history_id);
    expect(result.rows.map(row => [String(row[0]), Number(row[1])])).toEqual(reference.top_products.slice(0, 2).map((row: unknown[]) => [String(row[0]), Number(row[1])]));
    await page.goto(input.analysis_url); await expect(page.locator('.analysis-report h2')).toBeVisible();
    await page.goto(input.saved_url); await expect(page.getByRole('table')).toBeVisible();
    const requery = page.waitForResponse(r => r.url().endsWith('/requery'), { timeout: 240000 });
    await page.getByRole('button', { name: '重新查询当前数据', exact: true }).click();
    const newBody = await (await requery).json(); querySnapshot(newBody.turn.snapshot);
    expect(newBody.history.id).not.toBe(input.ranked_history_id);
    await expect(page.getByRole('button', { name: '另存成果', exact: true })).toBeVisible();
    const newUrl = page.url();
    await page.goto(input.saved_url); page.on('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '删除成果', exact: true }).click();
    await page.goto(newUrl); await expect(page.getByRole('table')).toBeVisible();
    await page.getByRole('button', { name: '退出登录', exact: true }).click();
    evidence.r3_after_restart = { top_n_continuation_reference: true, committed_analysis_after_expiry: true, requery_new_history: true, delete_saved_keeps_history: true, new_login_blank: true };
    evidence.status = 'passed';
  } catch (error) { evidence.status = 'failed'; evidence.step = 'r3-restart'; evidence.error_type = (error as Error).name; throw new Error('R3重启验收未通过，请检查私有报告。'); }
  finally { writeFileSync('/reports/browser.json', JSON.stringify(evidence, null, 2)); }
});
