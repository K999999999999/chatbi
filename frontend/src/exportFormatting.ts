import { displayValue, type DisplayColumn } from './numberFormat';

export type ExportCellValue = { displayed: string; original?: string };

export function exportCellValue(value: unknown, column: DisplayColumn, synthetic = false): ExportCellValue {
  if (synthetic) return { displayed: '缺失时段' };
  if (value === null) return { displayed: 'NULL（无数据）' };
  const displayed = displayValue(value, column);
  if (displayed === String(value)) return { displayed };
  return { displayed, original: value === '' ? '""' : String(value) };
}
