import type { TableData } from './results';
import type { DisplayColumn } from './numberFormat';

export type ChartPoint = { label: string; key: string; value: number | null; rowIndex: number };
export type ChartPlan = { id: string; title: string; kind: 'time' | 'category' | 'contribution';
  series: { column: DisplayColumn; points: ChartPoint[]; rawValues: unknown[] }[]; truncated: boolean };
export type ChartPlans = { plans: ChartPlan[]; reason?: string };

export function plotNumber(value: unknown, column: DisplayColumn): number | null | undefined {
  if (value === null) return null;
  if (typeof value !== 'number' && typeof value !== 'string') return;
  if (!/^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(String(value))) return;
  let n = Number(value);
  const nonzero = /[1-9]/.test(String(value).split(/[eE]/)[0]);
  if (!Number.isFinite(n) || Math.abs(n) > Number.MAX_SAFE_INTEGER || n === 0 && nonzero) return;
  if (column.format === 'ratio') n *= 100;
  if (!Number.isFinite(n) || Math.abs(n) > Number.MAX_SAFE_INTEGER) return;
  return n;
}

function nextPeriod(key: string, grain: string): string | undefined {
  const date = new Date(key + 'T00:00:00Z');
  if (grain === 'month') date.setUTCMonth(date.getUTCMonth() + 1);
  else if (grain === 'quarter') date.setUTCMonth(date.getUTCMonth() + 3);
  else if (grain === 'year') date.setUTCFullYear(date.getUTCFullYear() + 1);
  else if (grain === 'day' || grain === 'week') date.setUTCDate(date.getUTCDate() + (grain === 'week' ? 7 : 1));
  else return;
  if (!Number.isFinite(date.valueOf())) return;
  return date.toISOString().slice(0, 10);
}

function timePoints(keys: string[], values: (number | null)[], grain: string): ChartPoint[] {
  const points = keys.map((key, rowIndex) => ({ key, label: key, rowIndex, value: values[rowIndex] })).sort((a, b) => a.key.localeCompare(b.key));
  const result: ChartPoint[] = [];
  let budget = 2000;
  for (const point of points) {
    const previous = result.at(-1);
    let key = previous ? nextPeriod(previous.key, grain) : undefined;
    while (key && key < point.key && budget > 0) {
      result.push({ key, label: key, value: null, rowIndex: -1 });
      key = nextPeriod(key, grain); budget--;
    }
    if (key && key < point.key) result.push({ key: 'gap:' + point.key, label: '缺失时段', value: null, rowIndex: -1 });
    result.push(point);
  }
  return result;
}

export function buildChartPlans(data: TableData): ChartPlans {
  const meta = data.result_metadata;
  if (!data.rows.length) return { plans: [] };
  if (!meta) return { plans: [], reason: '结果含义未确认，仅展示表格。' };
  if (meta.scope.warnings.includes('GROUPING_UNCONFIRMED')) return { plans: [], reason: '分组含义未确认，仅展示表格。' };
  const groups = meta.scope.grouping;
  if (groups.length > 1) return { plans: [], reason: '多个分组维度：请通过追问改为单一分组后查看图表。' };
  if (!groups.length) return { plans: [] };
  const group = groups[0];
  if (group.kind === 'time' && !meta.time_axis) return { plans: [], reason: '时间含义未确认，仅展示表格。' };
  const keys = group.kind === 'time' ? meta.time_axis!.keys : data.rows.map(row => JSON.stringify(group.column_indices.map(i => row[i])));
  if (new Set(keys).size !== keys.length) return { plans: [], reason: '同一分组存在多行，不自动合并，仅展示表格。' };
  const plans = new Map<string, ChartPlan>();
  for (const column of meta.columns.filter(c => c.certified && c.role === 'metric' && c.unit)) {
    const values = data.rows.map(row => plotNumber(row[column.index], column));
    if (values.some(v => v === undefined) || !values.some(v => v !== null)) continue;
    const points: ChartPoint[] = group.kind === 'time' ? timePoints(keys, values as (number | null)[], meta.time_axis!.granularity)
      : keys.map((key, rowIndex) => ({ key, label: String(data.rows[rowIndex][group.column_indices[0]] ?? '无数据（空值）'), rowIndex, value: values[rowIndex] as number | null }));
    const unit = column.unit!;
    let plan = plans.get(unit.key);
    if (!plan) { plan = { id: unit.key, title: `${group.semantic_name} · ${unit.label}`, kind: group.kind, series: [], truncated: data.truncated }; plans.set(unit.key, plan); }
    plan.series.push({ column, points, rawValues: data.rows.map(row => row[column.index]) });
  }
  return { plans: [...plans.values()], reason: !plans.size ? '没有含义、单位和数值均可可靠绘图的指标，保留表格。' : undefined };
}
