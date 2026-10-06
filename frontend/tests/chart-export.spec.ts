import { test, expect } from '@playwright/test';
import { buildChartOption, wrapLabelByMeasurement } from '../src/chartOptions';
import { exportCellValue } from '../src/exportFormatting';
import { resolveExportChart } from '../src/exportPlan';
import type { ChartPlan } from '../src/chartPlan';
import type { ResultMetadata } from '../src/resultMetadata';

const metadata: ResultMetadata = { version: 1, status: 'complete', columns: [
  { index: 0, name: 'product', role: 'dimension', certified: true, semantic_name: '产品', definition: null, unit: null, format: 'raw' },
  { index: 1, name: 'sales', role: 'metric', certified: true, semantic_name: '人民币净销售额', definition: '定义', unit: { key: 'CNY', label: '元' }, format: 'money' }],
  scope: { status: 'complete', time_status: 'unknown', time: null, filters: [], grouping: [{ semantic_name: '产品', kind: 'category', column_indices: [0] }], warnings: [] },
  time_axis: null };

const plan: ChartPlan = { id: 'CNY', title: '产品 · 元', kind: 'category', truncated: true, series: [{
  column: metadata.columns[1], rawValues: Array.from({ length: 18 }, (_, i) => String(i + 1)),
  points: Array.from({ length: 18 }, (_, i) => ({ key: String(i), label: `产品${i + 1}`, rowIndex: i, value: i + 1 })),
}] };

const query = { mode: 'query', columns: ['product', 'sales'], rows: [['产品A', '10'], ['产品B', '20']], row_count: 2, truncated: false, result_metadata: metadata };

test('导出 option 展示全部分类、不启用缩放且图例不会滚动隐藏', () => {
  const option = buildChartOption(plan, 'bar', 'export') as Record<string, any>;
  expect(option.dataZoom).toEqual([]);
  expect(option.legend.type).toBe('plain');
  expect(option.yAxis.data).toHaveLength(18);
  expect(option.series[0].data).toHaveLength(18);
});

test('网页 option 继续使用滚动图例和长分类缩放', () => {
  const option = buildChartOption(plan, 'bar', 'web') as Record<string, any>;
  expect(option.legend.type).toBe('scroll');
  expect(option.dataZoom).toHaveLength(1);
  expect(option.grid.right).toBe(35);
  expect(option.yAxis.axisLabel).toEqual({ width: 160, overflow: 'truncate' });
  const timeOption = buildChartOption({ ...plan, kind: 'time' }, 'line', 'web') as Record<string, any>;
  expect(timeOption.xAxis.axisLabel).toBeUndefined();
  expect(timeOption.xAxis.nameLocation).toBeUndefined();
});

test('密集时间图在 PNG 中旋转显示全部日期并留出完整标签空间', () => {
  const timePlan = { ...plan, kind: 'time' as const };
  const option = buildChartOption(timePlan, 'line', 'export') as Record<string, any>;
  expect(option.xAxis.data).toHaveLength(18);
  expect(option.xAxis.axisLabel.rotate).toBe(90);
  expect(option.grid.bottom).toBe(360);
  expect(option.dataZoom).toEqual([]);
});

test('按文字测量换行且不删减标签字符', () => {
  const source = '客户区域华东大区';
  const wrapped = wrapLabelByMeasurement(source, text => [...text].length * 10, 40);
  expect(wrapped.replaceAll('\n', '')).toBe(source);
  expect(wrapped.split('\n').every(line => line.length <= 4)).toBe(true);
});

test('PNG 表格区分 NULL、空字符串、缺失时段并保留格式化数值原值', () => {
  expect(exportCellValue(null, metadata.columns[1])).toEqual({ displayed: 'NULL（无数据）' });
  expect(exportCellValue('无数据', metadata.columns[1])).toEqual({ displayed: '无数据' });
  expect(exportCellValue('', metadata.columns[1])).toEqual({ displayed: '空字符串', original: '""' });
  expect(exportCellValue(null, metadata.columns[1], true)).toEqual({ displayed: '缺失时段' });
  expect(exportCellValue('123.456', metadata.columns[1])).toEqual({ displayed: '123.46 元', original: '123.456' });
});

test('query 图按服务端快照计划选择，并拒绝不存在的图或类型', () => {
  const selected = resolveExportChart({ kind: 'query', result: query }, { chart_id: 'CNY', chart_type: 'bar' });
  expect(selected.plan.series[0].points.map(point => point.label)).toEqual(['产品A', '产品B']);
  expect(() => resolveExportChart({ kind: 'query', result: query }, { chart_id: 'ratio', chart_type: 'bar' })).toThrow();
  expect(() => resolveExportChart({ kind: 'query', result: query }, { chart_id: 'CNY', chart_type: 'line' })).toThrow();
});

test('analysis factors 必须绑定所选产品，任务图只能读取完成任务的快照', () => {
  const analysis = { mode: 'analysis', analysis_run_id: 'run-1', report: { attribution: {
    metric_name: '人民币净销售额', comparison_period: '2025年1月', current_period: '2025年2月',
    comparison_value: '10', current_value: '20', total_change: '10', direction: 'increase', omitted_product_count: 0,
    products: [{ product_name: '产品A', change: '10', classification: 'continuing', effect_on_metric: 'increases_target_metric',
      factors: [{ name: '销量效应', amount: '10', effect_on_metric: 'increases_target_metric' }] }],
  } }, task_results: [{ task_id: 'task-1', status: 'completed', ...query }] };
  const factor = resolveExportChart({ kind: 'analysis', result: analysis }, { chart_id: 'factors', chart_type: 'bar', product_index: 0 });
  expect(factor.plan.title).toContain('产品A');
  const task = resolveExportChart({ kind: 'analysis', result: analysis }, { chart_id: 'CNY', chart_type: 'bar', task_id: 'task-1' });
  expect(task.plan.series[0].points).toHaveLength(2);
  expect(() => resolveExportChart({ kind: 'analysis', result: analysis }, { chart_id: 'factors', chart_type: 'bar' })).toThrow();
  expect(() => resolveExportChart({ kind: 'analysis', result: analysis }, { chart_id: 'CNY', chart_type: 'bar', task_id: 'missing' })).toThrow();
});
