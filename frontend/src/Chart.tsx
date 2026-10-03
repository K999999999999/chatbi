import { useEffect, useRef, useState } from 'react';
import type { EChartsCoreOption } from 'echarts/core';
import type { CallbackDataParams } from 'echarts/types/dist/shared';
import type { ChartPlan } from './chartPlan';
import { displayValue, roundedToZero } from './numberFormat';

export function DataChart({ plan }: { plan: ChartPlan }) {
  const target = useRef<HTMLDivElement>(null);
  const [kind, setKind] = useState<'line' | 'bar'>(plan.kind === 'time' ? 'line' : 'bar');
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
      const option: EChartsCoreOption = {
        animation: false, aria: { enabled: true, label: { description: `${plan.title}，具体数据可在表格核对。` } },
        grid: { left: horizontal ? 180 : 90, right: 35, bottom: 65, top: 65 },
        legend: { type: 'scroll', top: 0 },
        tooltip: { trigger: 'item', renderMode: 'richText', formatter: (p: CallbackDataParams) => {
          const series = plan.series[p.seriesIndex ?? 0];
          const point = series?.points[p.dataIndex];
          if (!series || !point || point.rowIndex < 0) return '缺失时段：无数据';
          const raw = series.rawValues[point.rowIndex];
          const note = roundedToZero(raw, series.column) ? '（显示值已舍入）' : '';
          return `${point.label}\n${series.column.semantic_name}：${displayValue(raw, series.column)}${note}\n原始值：${String(raw)}`;
        } },
        xAxis: horizontal ? { type: 'value', name: plan.series[0]?.column.unit?.label } : { type: 'category', data: labels },
        yAxis: horizontal ? { type: 'category', data: labels, inverse: true, axisLabel: { width: 160, overflow: 'truncate' } } : { type: 'value', name: plan.series[0]?.column.unit?.label },
        dataZoom: labels.length > 15 ? [{ type: 'slider', yAxisIndex: horizontal ? 0 : undefined, xAxisIndex: horizontal ? undefined : 0, filterMode: 'none', start: 0, end: 15 / labels.length * 100 }] : [],
        series: plan.series.map(series => ({ name: series.column.semantic_name ?? series.column.name,
          type: kind, connectNulls: false, showSymbol: true,
          data: series.points.map(point => ({ value: point.value,
            itemStyle: plan.kind === 'contribution' ? { color: (point.value ?? 0) < 0 ? '#ad4b43' : '#146b68' } : undefined })) })),
      };
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
    {failed && <p role="status">图表不可用，已有数值与表格仍可查看。</p>}
    <div ref={target} hidden={failed} className="chart-canvas" data-chart-kind={kind} style={{ height: horizontal ? Math.max(260, Math.min(labels.length, 15) * 32 + 110) : 340 }}/>
  </section>;
}
