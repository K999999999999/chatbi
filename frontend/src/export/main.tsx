import { createRoot, type Root } from 'react-dom/client';
import { useEffect, useMemo, useState } from 'react';
import { init } from '../echartsRuntime';
import { buildChartOption, wrapLabelByMeasurement } from '../chartOptions';
import { resolveExportChart, type ChartExportSelection, type ChartExportSource } from '../exportPlan';
import { exportCellValue } from '../exportFormatting';
import { createPdfManifest, PdfReport, type PdfManifest, type PdfRenderRequest } from './pdfReport';
import './export.css';

const PNG_WIDTH = 1600;
const MAX_PNG_PIXELS = 40_000_000;
const ORIGIN = 'http://localhost';

type RenderRequest = { source: ChartExportSource; selection: ChartExportSelection; render_hash: string };
type RenderManifest = { version: 1; render_hash: string; chart_id: string; chart_type: string;
  task_id: string | null; product_index: number | null; category_count: number; series_count: number;
  width: number; height: number; labels_hash: string };

declare global {
  interface Window {
    __chatbiRenderChart?: (request: RenderRequest) => void;
    __chatbiRenderReport?: (request: PdfRenderRequest) => void;
    __chatbiRenderState?: { status: 'idle' | 'rendering' | 'ready' | 'failed'; manifest?: RenderManifest | PdfManifest; error?: string; code?: string };
  }
}

function ExportChart({ request }: { request: RenderRequest }) {
  const [state, setState] = useState<{ status: 'rendering' | 'ready' | 'failed'; manifest?: RenderManifest; error?: string; code?: string }>({ status: 'rendering' });
  const [target, setTarget] = useState<HTMLDivElement | null>(null);
  const [fontReady, setFontReady] = useState(false);
  const resolved = useMemo(() => resolveExportChart(request.source, request.selection), [request]);
  const { plan } = resolved;
  const points = plan.series[0]?.points ?? [];
  useEffect(() => {
    let active = true;
    void document.fonts.ready.then(() => { if (active) setFontReady(true); });
    return () => { active = false; };
  }, []);
  const axisLabels = useMemo(() => {
    if (!fontReady) return points.map(point => point.label);
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (!context) throw new Error('字体测量不可用');
    context.font = '16px "ChatBI Export Noto CJK SC", sans-serif';
    return points.map(point => wrapLabelByMeasurement(point.label, value => context.measureText(value).width, 300));
  }, [fontReady, points]);
  const lineHeights = axisLabels.map(label => label.split('\n').length);
  const categoryHeight = plan.kind === 'time'
    ? 660 + Math.min(120, Math.max(0, ...points.map(point => point.label.length)) * 12)
    : 280 + lineHeights.reduce((sum, count) => sum + Math.max(1, count) * 23 + 11, 0);
  const dataTableHeight = 90 + points.reduce((sum, point) => {
    const categoryLines = Math.max(1, wrapLabelByMeasurement(point.label, value => value.length * 8, 58).split('\n').length);
    const valueLines = Math.max(1, ...plan.series.map(series => {
      const raw = point.rowIndex < 0 ? '' : String(series.rawValues[point.rowIndex] ?? '');
      return Math.ceil(raw.length / Math.max(12, Math.floor(76 / plan.series.length)));
    }));
    return sum + Math.max(categoryLines, valueLines) * 22 + 12;
  }, 0);
  const estimatedHeight = Math.ceil(190 + categoryHeight + dataTableHeight);

  useEffect(() => {
    let active = true;
    let chart: ReturnType<typeof init> | undefined;
    async function render() {
      try {
        if (!fontReady || !points.length || !plan.series.length) return;
        if (!document.fonts.check('16px "ChatBI Export Noto CJK SC"', '中文图表')) throw new Error('中文字体不可用');
        if (PNG_WIDTH * estimatedHeight > MAX_PNG_PIXELS) {
          const error = '完整图表超过 PNG 像素限制';
          setState({ status: 'failed', code: 'EXPORT_PIXEL_LIMIT', error });
          window.__chatbiRenderState = { status: 'failed', code: 'EXPORT_PIXEL_LIMIT', error };
          return;
        }
        if (!target) return;
        chart = init(target, undefined, { renderer: 'svg' });
        const labels = [...plan.series[0].points].map(point => point.label);
        const labelsHash = await hashText(JSON.stringify(labels));
        const manifestBase = { version: 1 as const, render_hash: request.render_hash,
          chart_id: plan.id, chart_type: request.selection.chart_type, task_id: request.selection.task_id ?? null,
          product_index: request.selection.product_index ?? null, category_count: points.length,
          series_count: plan.series.length, labels_hash: labelsHash };
        let finalized = false;
        chart.on('finished', () => {
          if (!active || finalized) return;
          finalized = true;
          void (async () => {
            const svg = target?.querySelector('svg');
            if (!svg || svg.getBoundingClientRect().width < 1400 || svg.getBoundingClientRect().height < categoryHeight - 40) {
              setState({ status: 'failed', error: '图表未完整渲染' });
              window.__chatbiRenderState = { status: 'failed', error: '图表未完整渲染' };
              return;
            }
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            const width = document.documentElement.scrollWidth;
            const height = document.documentElement.scrollHeight;
            if (width !== PNG_WIDTH || width * height > MAX_PNG_PIXELS) {
              const error = '完整图表超过 PNG 像素限制';
              setState({ status: 'failed', code: 'EXPORT_PIXEL_LIMIT', error });
              window.__chatbiRenderState = { status: 'failed', code: 'EXPORT_PIXEL_LIMIT', error };
              return;
            }
            const manifest: RenderManifest = { ...manifestBase, width, height };
            setState({ status: 'ready', manifest });
            window.__chatbiRenderState = { status: 'ready', manifest };
          })();
        });
        chart.setOption(buildChartOption(plan, request.selection.chart_type, 'export', axisLabels));
      } catch (error) {
        const message = error instanceof Error ? error.message : '图表渲染失败';
        if (active) {
          setState({ status: 'failed', error: message });
          window.__chatbiRenderState = { status: 'failed', error: message };
        }
      }
    }
    void render();
    return () => { active = false; chart?.dispose(); };
  }, [target, fontReady, plan, request, axisLabels, points, estimatedHeight, categoryHeight, dataTableHeight]);

  const metadata = plan.series[0]?.column;
  const sourceResult = request.source.result as Record<string, unknown>;
  const report = sourceResult.report && typeof sourceResult.report === 'object' ? sourceResult.report as Record<string, unknown> : null;
  const attribution = report?.attribution && typeof report.attribution === 'object'
    ? report.attribution as Record<string, unknown> : null;
  const attributionContext = request.source.kind === 'analysis' && !request.selection.task_id && attribution
    ? `指标：${String(attribution.metric_name ?? '')} · 对比期间：${String(attribution.comparison_period ?? '未知')} · 当前期间：${String(attribution.current_period ?? '未知')}`
    : null;
  const taskData = request.selection.task_id && Array.isArray(sourceResult.task_results)
    ? (sourceResult.task_results as Record<string, unknown>[]).find(task => task.task_id === request.selection.task_id)
    : undefined;
  const queryMetadata = request.source.kind === 'query' ? sourceResult.result_metadata : taskData?.result_metadata;
  const scope = queryMetadata;
  const scopeTime = scope && typeof scope === 'object' ? (scope as Record<string, unknown>).scope : null;
  const time = scopeTime && typeof scopeTime === 'object' ? (scopeTime as Record<string, unknown>).time : null;
  const timeText = time && typeof time === 'object'
    ? `查询时间：${String((time as Record<string, unknown>).start)} 至 ${String((time as Record<string, unknown>).end_exclusive)} 前 · ${String((time as Record<string, unknown>).time_basis)}`
    : scopeTime && typeof scopeTime === 'object' && (scopeTime as Record<string, unknown>).time_status === 'unbounded'
      ? '查询时间：未限定时间范围。'
      : null;

  return <main className="export-page" data-export-state={state.status} data-testid="export-page">
    <h1>{plan.title}</h1>
    <p className="export-meta">来源：{request.source.kind === 'query' ? '成功问数快照' : '经营分析成功快照'} · 图表类型：{request.selection.chart_type === 'line' ? '折线图' : '柱状图'}</p>
    {metadata?.unit && <p className="export-meta">指标单位：{metadata.unit.label}</p>}
    {attributionContext && <p className="export-meta">{attributionContext}</p>}
    {timeText && <p className="export-meta">{timeText}</p>}
    {plan.kind === 'contribution' && request.selection.chart_id === 'factors' && request.selection.product_index !== undefined
      && <p className="export-meta">所选产品：{plan.title.replace(/ · 因素贡献$/, '')}</p>}
    {plan.truncated && <p className="export-warning">结果已截断，图表仅包含快照返回的部分数据，不代表完整结果。</p>}
    {plan.kind === 'contribution' && <p className="export-meta">正值表示增加目标指标，负值表示降低，零表示无变化。</p>}
    <section className="export-chart" aria-label={plan.title}>
      <div ref={setTarget} className="export-chart-canvas" style={{ height: categoryHeight }}/>
    </section>
    <table className="export-data" aria-label="图表完整数据">
      <thead><tr><th>{plan.kind === 'time' ? '查询时间点' : '分类'}</th>{plan.series.map((series, index) =>
        <th key={index}>{series.column.semantic_name ?? series.column.name}{series.column.unit ? `（${series.column.unit.label}）` : ''}</th>)}</tr></thead>
      <tbody>{points.map((point, index) => <tr key={`${point.key}-${index}`}>
        <td>{point.label}</td>{plan.series.map((series, seriesIndex) => {
          const synthetic = point.rowIndex < 0;
          const raw = synthetic ? undefined : series.rawValues[point.rowIndex];
          const cell = exportCellValue(raw, series.column, synthetic);
          return <td key={seriesIndex}><span>{cell.displayed}</span>{cell.original !== undefined && <small>原始值：{cell.original}</small>}</td>;
        })}</tr>)}</tbody>
    </table>
    <p className="export-footer">图形按当前成功快照生成；不重新查询。导出时间：{String(request.source.export_time ?? '')}</p>
    {state.status === 'failed' && <p role="alert">{state.error}</p>}
  </main>;
}

async function hashText(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

let root: Root | undefined;
window.__chatbiRenderState = { status: 'idle' };
window.__chatbiRenderChart = request => {
  if (root) throw new Error('渲染入口不可重复调用');
  window.__chatbiRenderState = { status: 'rendering' };
  try { resolveExportChart(request.source, request.selection); }
  catch {
    window.__chatbiRenderState = { status: 'failed', code: 'EXPORT_SELECTION_INVALID', error: '所选图表不可用' };
    return;
  }
  root = createRoot(document.getElementById('root')!);
  root.render(<ExportChart request={request}/>);
};
window.__chatbiRenderReport = request => {
  if (root) throw new Error('渲染入口不可重复调用');
  window.__chatbiRenderState = { status: 'rendering' };
  try { createPdfManifest(request); }
  catch (error) {
    window.__chatbiRenderState = { status: 'failed', code: 'PDF_RENDER_FAILED',
      error: error instanceof Error ? error.message : 'PDF 快照无效' };
    return;
  }
  root = createRoot(document.getElementById('root')!);
  root.render(<PdfReport request={request}/>);
};

export { ORIGIN };
