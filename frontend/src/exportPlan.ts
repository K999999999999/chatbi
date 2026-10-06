import { buildChartPlans, buildContributionPlan, contributionColumn, type ChartPlan } from './chartPlan';
import type { TableData } from './results';
import type { ChartType } from './chartOptions';
import { decodeMetadata } from './resultMetadata';

export type ChartExportSelection = {
  chart_id: string;
  chart_type: ChartType;
  task_id?: string;
  product_index?: number;
};

export type ChartExportSource = { kind: 'query' | 'analysis'; result: unknown; export_time?: string };

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('导出图表来源无效');
  return value as Record<string, unknown>;
}

function tableData(value: unknown): TableData {
  const item = record(value);
  const columns = item.columns;
  const rows = item.rows;
  if (!Array.isArray(columns) || !columns.every(name => typeof name === 'string')
      || !Array.isArray(rows) || !rows.every(row => Array.isArray(row) && row.length === columns.length
        && row.every(cell => cell === null || typeof cell === 'string' || typeof cell === 'boolean'
          || typeof cell === 'number' && Number.isFinite(cell)))
      || !Number.isSafeInteger(item.row_count) || Number(item.row_count) < rows.length
      || typeof item.truncated !== 'boolean' || (item.row_count !== rows.length && !item.truncated)) {
    throw new Error('导出图表结果快照无效');
  }
  return { columns, rows, row_count: Number(item.row_count), truncated: item.truncated,
    result_metadata: decodeMetadata(item.result_metadata, columns, rows.length) };
}

function choosePlan(plans: ChartPlan[], selection: ChartExportSelection): ChartPlan {
  const plan = plans.find(item => item.id === selection.chart_id);
  if (!plan) throw new Error('所选图表不可用');
  if (plan.kind === 'time' ? !['line', 'bar'].includes(selection.chart_type) : selection.chart_type !== 'bar') {
    throw new Error('所选图表类型不可用');
  }
  return plan;
}

function queryPlan(value: unknown, selection: ChartExportSelection): ChartPlan {
  if (selection.task_id !== undefined || selection.product_index !== undefined) throw new Error('图表选择与来源不匹配');
  return choosePlan(buildChartPlans(tableData(value)).plans, selection);
}

function analysisPlan(value: unknown, selection: ChartExportSelection): ChartPlan {
  const analysis = record(value);
  if (analysis.mode !== 'analysis' || !Array.isArray(analysis.task_results)) throw new Error('分析图表来源无效');
  if (selection.task_id !== undefined) {
    if (selection.product_index !== undefined) throw new Error('图表选择与来源不匹配');
    const task = analysis.task_results.map(record).find(item => item.task_id === selection.task_id && item.status === 'completed');
    if (!task) throw new Error('所选分析任务没有可用结果');
    return choosePlan(buildChartPlans(tableData(task)).plans, selection);
  }
  const report = record(analysis.report);
  const attribution = record(report.attribution);
  if (!Array.isArray(attribution.products)) throw new Error('所选分析图表不可用');
  const column = contributionColumn(String(attribution.metric_name ?? ''));
  if (selection.chart_id === 'products' && selection.product_index === undefined) {
    const plan = buildContributionPlan('products', '主要产品变化贡献', attribution.products.map(value => {
      const product = record(value);
      return { label: String(product.product_name ?? ''), amount: String(product.change ?? '') };
    }), column);
    if (!plan) throw new Error('所选分析图表不可用');
    return choosePlan([plan], selection);
  }
  if (selection.chart_id === 'factors' && Number.isSafeInteger(selection.product_index)) {
    const product = record(attribution.products[selection.product_index!]);
    if (!Array.isArray(product.factors)) throw new Error('所选产品因素图不可用');
    const plan = buildContributionPlan('factors', `${String(product.product_name ?? '')} · 因素贡献`, product.factors.map(value => {
      const factor = record(value);
      return { label: String(factor.name ?? ''), amount: String(factor.amount ?? '') };
    }), column);
    if (!plan) throw new Error('所选产品因素图不可用');
    return choosePlan([plan], selection);
  }
  throw new Error('所选分析图表不可用');
}

export function resolveExportChart(source: ChartExportSource, selection: ChartExportSelection): { plan: ChartPlan } {
  if (!selection.chart_id || selection.chart_id.length > 80) throw new Error('图表选择无效');
  const plan = source.kind === 'query'
    ? queryPlan(source.result, selection)
    : source.kind === 'analysis'
      ? analysisPlan(source.result, selection)
      : (() => { throw new Error('导出图表来源无效'); })();
  return { plan };
}
