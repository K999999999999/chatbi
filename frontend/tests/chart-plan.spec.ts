import { test, expect } from '@playwright/test';
import { buildChartPlans } from '../src/chartPlan';
import type { TableData } from '../src/results';
import type { ResultMetadata } from '../src/resultMetadata';

const metadata: ResultMetadata = { version: 1, status: 'complete', columns: [
  { index: 0, name: 'month', role: 'dimension', certified: true, semantic_name: '月份', definition: null, unit: null, format: 'raw' },
  { index: 1, name: 'sales', role: 'metric', certified: true, semantic_name: '人民币净销售额', definition: '定义', unit: { key: 'CNY', label: '元' }, format: 'money' }],
  scope: { status: 'complete', time_status: 'confirmed', time: null, filters: [], grouping: [{ semantic_name: '月份', kind: 'time', column_indices: [0] }], warnings: [] },
  time_axis: { granularity: 'month', keys: ['2025-03-01', '2025-01-01'] } };
const data: TableData = { columns: ['month', 'sales'], rows: [['2025-03', '20'], ['2025-01', '10']], row_count: 2, truncated: false, result_metadata: metadata };

test('时间图排序并用空点断开缺月，原表格保持顺序', () => {
  const result = buildChartPlans(data);
  expect(result.plans).toHaveLength(1);
  expect(result.plans[0].series[0].points.map(p => [p.key, p.value])).toEqual([['2025-01-01', 10], ['2025-02-01', null], ['2025-03-01', 20]]);
  expect(data.rows[0][0]).toBe('2025-03');
});
test('不同单位拆图，重复分组安全降级，截断标识保留', () => {
  const mixed: TableData = { ...data, columns: [...data.columns, 'rate'], rows: [['2025-03', '20', '0.1'], ['2025-01', '10', '0.2']], truncated: true,
    result_metadata: { ...metadata, columns: [...metadata.columns, { ...metadata.columns[1], index: 2, name: 'rate', semantic_name: '毛利率', format: 'ratio', unit: { key: 'ratio', label: '%' } }] } };
  expect(buildChartPlans(mixed).plans).toHaveLength(2);
  expect(buildChartPlans(mixed).plans.every(p => p.truncated)).toBe(true);
  expect(buildChartPlans({ ...data, result_metadata: { ...metadata, time_axis: { granularity: 'month', keys: ['2025-01-01', '2025-01-01'] } } }).plans).toHaveLength(0);
});
test('没有可信语义或多个分组时只保留表格', () => {
  expect(buildChartPlans({ ...data, result_metadata: undefined }).plans).toHaveLength(0);
  expect(buildChartPlans({ ...data, result_metadata: { ...metadata, scope: { ...metadata.scope, grouping: [...metadata.scope.grouping, { semantic_name: '产品', kind: 'category', column_indices: [0] }] } } }).plans).toHaveLength(0);
});

test('不安全坐标降级，NULL保留为空而不是零，单点保留', () => {
  expect(buildChartPlans({ ...data, rows: [['2025-03', '9007199254740992'], ['2025-01', '10']] }).plans).toHaveLength(0);
  expect(buildChartPlans({ ...data, rows: [['2025-03', '1e-999'], ['2025-01', '10']] }).plans).toHaveLength(0);
  const nullable = buildChartPlans({ ...data, rows: [['2025-03', null], ['2025-01', '10']] });
  expect(nullable.plans[0].series[0].points.at(-1)?.value).toBeNull();
  const single = buildChartPlans({ ...data, rows: [['2025-03', '10']], row_count: 1, result_metadata: { ...metadata, time_axis: { granularity: 'month', keys: ['2025-03-01'] } } });
  expect(single.plans[0].series[0].points).toHaveLength(1);
});
