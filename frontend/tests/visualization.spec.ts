import { test, expect } from '@playwright/test';
import { login, send, mockFinalExecution } from './helpers';
const columns = ['month', 'sales', 'ratio'];
const metadata = { version: 1, status: 'complete', columns: [
  { index: 0, name: 'month', role: 'dimension', certified: true, semantic_name: '月份', definition: null, unit: null, format: 'raw' },
  { index: 1, name: 'sales', role: 'metric', certified: true, semantic_name: '人民币净销售额', definition: '已完成订单', unit: { key: 'CNY', label: '元' }, format: 'money' },
  { index: 2, name: 'ratio', role: 'metric', certified: true, semantic_name: '人民币毛利率', definition: '毛利 / 销售额', unit: { key: 'ratio', label: '%' }, format: 'ratio' }],
  scope: { status: 'complete', time_status: 'confirmed', time: { start: '2025-01-01', end_exclusive: '2026-01-01', time_basis: '订单完成日期' }, filters: [], grouping: [{ semantic_name: '月份', kind: 'time', column_indices: [0] }], warnings: [] },
  time_axis: { granularity: 'month', keys: ['2025-03-01', '2025-01-01'] } };
const payload = { request_id: 'r2', conversation_id: 'context', mode: 'query', sql: 'SELECT 1', columns,
  rows: [['2025-03', '1234567.895', '0.12345'], ['2025-01', null, '0']], row_count: 2, truncated: false, result_metadata: metadata };
test('图表和表格默认同显、不同单位拆图、切换折叠不请求', async ({ page }) => {
  await login(page); let calls = 0;
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/executions')) calls++; });
  await mockFinalExecution(page, payload);
  await send(page, '年度趋势');
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.locator('.chart-canvas svg')).toHaveCount(2);
  await expect(page.getByRole('cell').filter({ hasText: '1,234,567.90 元' })).toBeVisible();
  await expect(page.getByRole('cell').filter({ hasText: '12.35%' })).toBeVisible();
  await expect(page.getByRole('cell', { name: '无数据', exact: true })).toBeVisible();
  await page.getByLabel('图表类型').first().selectOption('bar');
  await expect(page.locator('[data-chart-kind="bar"] svg')).toHaveCount(1);
  await page.getByText('图表', { exact: true }).click();
  await expect(page.getByRole('table')).toBeVisible();
  await page.getByText('图表', { exact: true }).click();
  await page.getByText('查看原始值').first().click();
  await expect(page.getByText('1234567.895', { exact: true })).toBeVisible();
  expect(calls).toBe(1);
});
test('损坏元数据与零行仍保留成功结果和追问', async ({ page }) => {
  await login(page); let calls = 0;
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/executions')) calls++; });
  await mockFinalExecution(page, (current: unknown, call: number) => call === 1 ? { ...payload, result_metadata: { version: 99 } } : { ...payload, rows: [], row_count: 0, result_metadata: undefined });
  await send(page, '查询'); await expect(page.getByRole('table')).toBeVisible();
  await expect(page.locator('.chart-canvas')).toHaveCount(0);
  await send(page, '追问'); await expect(page.getByText('查询成功，没有匹配的数据。')).toBeVisible();
  expect(calls).toBe(2);
});
test('图表加载失败不丢表格，恶意标签只作文字', async ({ page }) => {
  await login(page);
  await mockFinalExecution(page, { ...payload, columns: ['<img src=x onerror=alert(1)>', 'sales', 'ratio'], result_metadata: { ...metadata, columns: [{ ...metadata.columns[0], name: '<img src=x onerror=alert(1)>' }, ...metadata.columns.slice(1)] } });
  await page.route('**/assets/echartsRuntime*', route => route.abort());
  await page.route('**/src/echartsRuntime.ts*', route => route.abort());
  await send(page, '查询'); await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByText('图表不可用，已有数值与表格仍可查看。')).toHaveCount(2);
  await expect(page.locator('.answer img')).toHaveCount(0);
});
test('经营归因选择产品使用既有因素，方向与金额格式保持一致', async ({ page }) => {
  await login(page); await page.getByRole('button', { name: '经营分析', exact: true }).click(); let calls = 0;
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/executions')) calls++; });
  await mockFinalExecution(page, (current: unknown) => {
    const body = current as Record<string, any>;
    body.report.attribution = { metric_name: '人民币毛利', comparison_period: '2025-01', current_period: '2025-02', comparison_value: '1000', current_value: '900', total_change: '-100', direction: 'decrease', reconciliation_passed: true, omitted_product_count: 2,
      products: [{ product_name: '持续产品A', change: '-150', classification: 'continuing', effect_on_metric: 'decreases_target_metric', factors: [{ name: '成本因素', amount: '-150', effect_on_metric: 'decreases_target_metric' }] }, { product_name: '新增产品B', change: '50', classification: 'new', effect_on_metric: 'increases_target_metric', factors: [{ name: '新增产品贡献', amount: '50', effect_on_metric: 'increases_target_metric' }] }] };
    return body;
  });
  await send(page, '分析2025年2月相比2025年1月的毛利变化');
  await expect(page.locator('.attribution .chart-canvas svg')).toHaveCount(2);
  await expect(page.getByText('-100.00 元', { exact: true })).toBeVisible();
  await expect(page.getByText('成本因素：-150.00 元 · 降低目标指标', { exact: true })).toBeVisible();
  await page.getByLabel('查看产品因素').selectOption('1');
  await expect(page.getByText('新增产品贡献：50.00 元 · 增加目标指标', { exact: true })).toBeVisible();
  await expect(page.getByText('另有 2 个产品未在主要贡献列表中展示。')).toBeVisible();
  expect(calls).toBe(1);
});

test('截断结果图和表都明确范围且保留100行', async ({ page }) => {
  await login(page);
  const rows = Array.from({ length: 100 }, (_, i) => [new Date(Date.UTC(2025, 0, i + 1)).toISOString().slice(0, 10), '1000', '0.1']);
  await mockFinalExecution(page, { ...payload, rows, row_count: 100, truncated: true,
    result_metadata: { ...metadata, time_axis: { granularity: 'day', keys: rows.map(row => row[0]) } } });
  await send(page, '按日查询');
  await expect(page.locator('.chart-canvas svg')).toHaveCount(2);
  await expect(page.getByRole('row')).toHaveCount(101);
  await expect(page.getByText('仅展示部分数据（最多100行），图表不代表完整结果。')).toHaveCount(2);
  await expect(page.getByText(/结果已截断/)).toBeVisible();
});

test('无变化、退出产品与缺因素不造归因，不完整证据仍提示', async ({ page }) => {
  await login(page); await page.getByRole('button', { name: '经营分析', exact: true }).click();
  await mockFinalExecution(page, (current: unknown) => {
    const body = current as Record<string, any>;
    body.report.attribution = { metric_name: '人民币净销售额', comparison_period: '2025-01', current_period: '2025-02', comparison_value: '0', current_value: '0', total_change: '0', direction: 'unchanged', reconciliation_passed: true, omitted_product_count: 0,
      products: [{ product_name: '退出产品', classification: 'discontinued', change: '0', effect_on_metric: 'no_change_to_target_metric', factors: [] }] };
    body.report.incomplete_tasks = [{ task_id: 'current-overall', reasons: ['返回结果已截断'] }];
    return body;
  });
  await send(page, '分析两期');
  await expect(page.getByText('期间变化方向：目标指标无变化；对账已通过。')).toBeVisible();
  await expect(page.getByText('退出产品：退出产品', { exact: true })).toBeVisible();
  await expect(page.getByText('没有可用因素，不补造价格或成本贡献。')).toBeVisible();
  await expect(page.locator('.attribution .chart-canvas svg')).toHaveCount(1);
  await expect(page.getByRole('heading', { name: '证据不完整' })).toBeVisible();
});

test('极小非零经营贡献显示舍入提示并保留后端方向和原值', async ({ page }) => {
  await login(page); await page.getByRole('button', { name: '经营分析', exact: true }).click();
  await mockFinalExecution(page, (current: unknown) => {
    const body = current as Record<string, any>;
    body.report.attribution = { metric_name: '人民币毛利', comparison_period: '2025-01', current_period: '2025-02', comparison_value: '1', current_value: '0.9999', total_change: '-0.0001', direction: 'decrease', reconciliation_passed: true, omitted_product_count: 0,
      products: [{ product_name: '产品A', classification: 'continuing', change: '-0.0001', effect_on_metric: 'decreases_target_metric', factors: [{ name: '成本因素', amount: '-0.0001', effect_on_metric: 'decreases_target_metric' }] }] };
    return body;
  });
  await send(page, '分析两期');
  await expect(page.getByText('微小非零贡献按两位小数显示为0.00；请核对原始值，变化方向仍采用后端结论。', { exact: true })).toBeVisible();
  await expect(page.getByText('期间变化方向：降低目标指标；对账已通过。')).toBeVisible();
  await page.locator('.attribution .metric-grid > div').last().getByText('查看原始值').click();
  await expect(page.locator('.attribution .metric-grid code').last()).toHaveText('-0.0001');
});
