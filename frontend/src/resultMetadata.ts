import { object } from './parse';
import type { DisplayColumn } from './numberFormat';

export type ResultMetadata = { version: 1; columns: DisplayColumn[]; status: string;
  scope: { status: string; time_status: string; time: { start: string; end_exclusive: string; time_basis: string } | null;
    filters: { label: string; operator: string; values: string[] }[];
    grouping: { semantic_name: string; kind: 'time' | 'category'; column_indices: number[] }[]; warnings: string[] };
  time_axis: { granularity: string; keys: string[] } | null };

function isoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value + 'T00:00:00Z');
  return Number.isFinite(date.valueOf()) && date.toISOString().slice(0, 10) === value;
}

export function decodeMetadata(value: unknown, names: string[], rowCount: number): ResultMetadata | undefined {
  try {
    const p = object(value);
    if (p.version !== 1 || !['complete', 'partial', 'unavailable'].includes(String(p.status)) || !Array.isArray(p.columns) || p.columns.length !== names.length) return;
    const columns = p.columns.map((value, index): DisplayColumn => {
      const fallback: DisplayColumn = { index, name: names[index], certified: false, role: 'unknown', semantic_name: null, definition: null, unit: null, format: 'raw' };
      try {
        const c = object(value);
        if (c.index !== index || c.name !== names[index] || c.certified !== true || !['metric', 'dimension', 'identifier'].includes(String(c.role))) return fallback;
        if (!['money', 'count', 'ratio', 'number', 'raw'].includes(String(c.format))) return fallback;
        if (c.role !== 'metric' && c.format !== 'raw') return fallback;
        if (typeof c.semantic_name !== 'string' || !c.semantic_name) return fallback;
        const unit = c.unit === null ? null : object(c.unit);
        if (unit && (typeof unit.key !== 'string' || typeof unit.label !== 'string' || !unit.key || !unit.label)) return fallback;
        if (c.format === 'money' && unit?.key !== 'CNY' || c.format === 'ratio' && unit?.key !== 'ratio') return fallback;
        return { index, name: names[index], certified: true, role: String(c.role), semantic_name: c.semantic_name,
          definition: typeof c.definition === 'string' ? c.definition : null,
          unit: unit ? { key: unit.key as string, label: unit.label as string } : null, format: c.format as DisplayColumn['format'] };
      } catch { return fallback; }
    });
    const scope = object(p.scope);
    if (!['complete', 'partial', 'unavailable'].includes(String(scope.status)) || !['confirmed', 'unbounded', 'unknown'].includes(String(scope.time_status))
      || !Array.isArray(scope.grouping) || !Array.isArray(scope.filters) || !Array.isArray(scope.warnings)) return;
    const grouping = scope.grouping.map(value => {
      const g = object(value);
      if (typeof g.semantic_name !== 'string' || !['time', 'category'].includes(String(g.kind)) || !Array.isArray(g.column_indices)
        || !g.column_indices.length || !g.column_indices.every(i => Number.isInteger(i) && i >= 0 && i < names.length && columns[i].role === 'dimension' && columns[i].certified)) throw new Error('分组无效');
      return g as ResultMetadata['scope']['grouping'][number];
    });
    const filters = scope.filters.map(value => {
      const f = object(value);
      if (typeof f.label !== 'string' || typeof f.operator !== 'string' || !Array.isArray(f.values) || !f.values.every(v => typeof v === 'string')) throw new Error('筛选无效');
      return f as ResultMetadata['scope']['filters'][number];
    });
    const time = scope.time === null ? null : object(scope.time);
    if (time && !['start', 'end_exclusive', 'time_basis'].every(k => typeof time[k] === 'string')) return;
    if (time && (!isoDate(time.start) || !isoDate(time.end_exclusive) || time.start >= time.end_exclusive)) return;
    if (scope.time_status === 'confirmed' && !time || scope.time_status !== 'confirmed' && time) return;
    let axis: ResultMetadata['time_axis'] = null;
    if (p.time_axis != null) {
      const a = object(p.time_axis);
      if (!['day', 'week', 'month', 'quarter', 'year'].includes(String(a.granularity)) || !Array.isArray(a.keys) || a.keys.length !== rowCount || !a.keys.every(isoDate)) return;
      axis = a as ResultMetadata['time_axis'];
    }
    return { version: 1, status: String(p.status), columns, scope: { status: String(scope.status), time_status: String(scope.time_status),
      time: time as ResultMetadata['scope']['time'], grouping, filters, warnings: scope.warnings.filter(v => typeof v === 'string') }, time_axis: axis };
  } catch { return; }
}
