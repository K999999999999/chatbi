import { test, expect } from '@playwright/test';
import { displayValue, type DisplayColumn } from '../src/numberFormat';

const money: DisplayColumn = { index: 0, name: 'value', certified: true, role: 'metric', semantic_name: '人民币毛利',
  definition: '定义', unit: { key: 'CNY', label: '元' }, format: 'money' };

test('金额十进制字符串保留精度并按半值远离零舍入', () => {
  expect(displayValue('9007199254740993.895', money)).toBe('9,007,199,254,740,993.90 元');
  expect(displayValue('-1234.895', money)).toBe('-1,234.90 元');
});
test('毛利率按十进制转百分比，计数不截去未知小数', () => {
  expect(displayValue('0.123456', { ...money, format: 'ratio', unit: { key: 'ratio', label: '%' } })).toBe('12.35%');
  expect(displayValue('12345', { ...money, format: 'count', unit: { key: 'order', label: '单' } })).toBe('12,345 单');
  expect(displayValue('1.2', { ...money, format: 'count' })).toBe('1.2');
});
test('编号不猜测格式；无数据、零、空字符串区分', () => {
  expect(displayValue('000123456')).toBe('000123456');
  expect(displayValue(null, money)).toBe('无数据');
  expect(displayValue(0, money)).toBe('0.00 元');
  expect(displayValue('', money)).toBe('空字符串');
});
