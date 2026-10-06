import { useEffect, useRef, useState } from 'react';
import type { ChartPlan } from './chartPlan';
import type { ExportSource } from './api';
import type { ChartType } from './chartOptions';
import { buildChartOption } from './chartOptions';
import { ChartExportButton } from './ChartExportButton';

export function DataChart({ plan, exportSource, canExport = false, taskId, productIndex, userId }:
  { plan: ChartPlan; exportSource?: ExportSource; canExport?: boolean; taskId?: string; productIndex?: number; userId?: number }) {
  const target = useRef<HTMLDivElement>(null);
  const [kind, setKind] = useState<ChartType>(plan.kind === 'time' ? 'line' : 'bar');
  const [failed, setFailed] = useState(false);
  const horizontal = plan.kind !== 'time';
  const labels = plan.series[0]?.points.map(p => p.label) ?? [];
  useEffect(() => {
    let active = true;
    let dispose: (() => void) | undefined;
    setFailed(false);
    void import('./echartsRuntime').then(({ init }) => {
      if (!active || !target.current) return;
      const chart = init(target.current, undefined, { renderer: 'svg' });
      dispose = () => chart.dispose();
      const resize = new ResizeObserver(() => { try { chart.resize(); } catch { if (active) setFailed(true); } });
      dispose = () => { resize.disconnect(); chart.dispose(); };
      const option = buildChartOption(plan, kind, 'web', labels);
      chart.setOption(option);
      resize.observe(target.current);
    }).catch(() => { if (active) { dispose?.(); dispose = undefined; setFailed(true); } });
    return () => { active = false; dispose?.(); };
  }, [plan, kind, horizontal]);
  return <section className="data-chart" aria-label={plan.title}>
    <h4>{plan.title}</h4>
    {plan.truncated && <p className="result-meta">仅展示部分数据（最多100行），图表不代表完整结果。</p>}
    {plan.kind === 'time' && <><label>图表类型 <select value={kind} onChange={e => setKind(e.target.value as 'line' | 'bar')}>
      <option value="line">折线图</option><option value="bar">柱状图</option></select></label>
      {plan.series[0]?.points.filter(p => p.rowIndex >= 0).length === 1 && <p>只有一个时间点，不作趋势判断。</p>}</>}
    {plan.kind === 'contribution' && <p>正值表示增加目标指标，负值表示降低，零表示无变化。</p>}
    {exportSource && userId !== undefined && <ChartExportButton source={exportSource} chartId={plan.id} chartType={kind}
      taskId={taskId} productIndex={productIndex} canExport={canExport} title={plan.title} userId={userId}/>}
    {failed && <p role="status">图表不可用，已有数值与表格仍可查看。</p>}
    <div ref={target} hidden={failed} className="chart-canvas" data-chart-kind={kind} style={{ height: horizontal ? Math.max(260, Math.min(labels.length, 15) * 32 + 110) : 340 }}/>
  </section>;
}
