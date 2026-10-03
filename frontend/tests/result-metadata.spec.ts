import { test, expect } from '@playwright/test';
import { decodeMetadata } from '../src/resultMetadata';
const column = { index: 0, name: 'x', role: 'metric', certified: true, semantic_name: '净销售额', definition: '定义', unit: { key: 'CNY', label: '元' }, format: 'money' };
const payload = { version: 1, status: 'complete', columns: [column], scope: { status: 'complete', time_status: 'unbounded', time: null, filters: [], grouping: [], warnings: [] }, time_axis: null };
test('未知版本、安全损坏范围和无效日期不成为绘图事实', () => {
  expect(decodeMetadata({ ...payload, version: 2 }, ['x'], 1)).toBeUndefined();
  expect(decodeMetadata({ ...payload, status: 'invented' }, ['x'], 1)).toBeUndefined();
  expect(decodeMetadata({ ...payload, time_axis: { granularity: 'month', keys: ['2025-02-31'] } }, ['x'], 1)).toBeUndefined();
  expect(decodeMetadata({ ...payload, time_axis: { granularity: 'invented', keys: ['2025-01-01'] } }, ['x'], 1)).toBeUndefined();
});
test('损坏列局部降级，编号不接受金额格式', () => {
  const decoded = decodeMetadata({ ...payload, columns: [column, { ...column, index: 1, name: 'id', role: 'identifier' }] }, ['x', 'id'], 1)!;
  expect(decoded.columns[0].certified).toBe(true);
  expect(decoded.columns[1].certified).toBe(false);
});
