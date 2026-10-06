import type { EChartsCoreOption } from 'echarts/core';
import type { CallbackDataParams } from 'echarts/types/dist/shared';
import type { ChartPlan } from './chartPlan';
import { displayValue, roundedToZero } from './numberFormat';

export type ChartType = 'line' | 'bar';
export type ChartProfile = 'web' | 'export';

export function wrapLabelByMeasurement(label: string, measure: (text: string) => number, width: number): string {
  const lines: string[] = [];
  let current = '';
  for (const part of label.split('\n')) {
    for (const character of part) {
      if (current && measure(current + character) > width) {
        lines.push(current);
        current = character;
      } else {
        current += character;
      }
    }
    lines.push(current);
    current = '';
  }
  return lines.join('\n');
}

export function buildChartOption(
  plan: ChartPlan,
  kind: ChartType,
  profile: ChartProfile,
  axisLabels: string[] = plan.series[0]?.points.map(point => point.label) ?? [],
): EChartsCoreOption {
  const exportMode = profile === 'export';
  const horizontal = plan.kind !== 'time';
  const denseTimeAxis = exportMode && !horizontal && axisLabels.length > 15;
  const labelWidth = exportMode ? 300 : 160;
  return {
    animation: false,
    aria: { enabled: true, label: { description: `${plan.title}，具体数据可在表格核对。` } },
    grid: {
      left: horizontal ? (exportMode ? 360 : 180) : 90,
      right: exportMode ? 45 : 35,
      bottom: exportMode ? (denseTimeAxis ? 360 : 115) : 65,
      top: exportMode ? 130 : 65,
      containLabel: false,
    },
    legend: exportMode
      ? { type: 'plain', top: 54, width: '92%', itemGap: 24, textStyle: { fontSize: 16 } }
      : { type: 'scroll', top: 0 },
    tooltip: {
      trigger: 'item', renderMode: 'richText', formatter: (p: CallbackDataParams) => {
        const series = plan.series[p.seriesIndex ?? 0];
        const point = series?.points[p.dataIndex];
        if (!series || !point || point.rowIndex < 0) return '缺失时段：无数据';
        const raw = series.rawValues[point.rowIndex];
        const note = roundedToZero(raw, series.column) ? '（显示值已舍入）' : '';
        return `${point.label}\n${series.column.semantic_name}：${displayValue(raw, series.column)}${note}\n原始值：${String(raw)}`;
      },
    },
    xAxis: horizontal
      ? { type: 'value', name: plan.series[0]?.column.unit?.label,
        ...(exportMode ? { nameLocation: 'middle', nameGap: 45 } : {}) }
      : { type: 'category', data: axisLabels,
        ...(exportMode ? { axisLabel: { interval: 0, hideOverlap: false, overflow: 'break', width: labelWidth,
          ...(denseTimeAxis ? { rotate: 90, fontSize: 10, margin: 12 } : {}) } } : {}) },
    yAxis: horizontal
      ? { type: 'category', data: axisLabels, inverse: true, axisLabel: exportMode
        ? { interval: 0, hideOverlap: false, width: labelWidth, overflow: 'break' }
        : { width: labelWidth, overflow: 'truncate' } }
      : { type: 'value', name: plan.series[0]?.column.unit?.label },
    dataZoom: !exportMode && plan.series[0] && plan.series[0].points.length > 15
      ? [{ type: 'slider', yAxisIndex: horizontal ? 0 : undefined, xAxisIndex: horizontal ? undefined : 0,
        filterMode: 'none', start: 0, end: 15 / plan.series[0].points.length * 100 }]
      : [],
    series: plan.series.map(series => ({
      name: series.column.semantic_name ?? series.column.name,
      type: kind,
      connectNulls: false,
      showSymbol: true,
      data: series.points.map(point => ({ value: point.value,
        itemStyle: plan.kind === 'contribution'
          ? { color: (point.value ?? 0) < 0 ? '#ad4b43' : '#146b68' }
          : undefined })),
    })),
  };
}
