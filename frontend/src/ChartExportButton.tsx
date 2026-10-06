import { useState } from 'react';
import { downloadResultExport, type ChartExportSelection, type ExportSource } from './api';

export function ChartExportButton({ source, chartId, chartType, taskId, productIndex, canExport, title, userId }: {
  source: ExportSource; chartId: string; chartType: 'line' | 'bar'; taskId?: string; productIndex?: number;
  canExport: boolean; title: string; userId: number;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selection: ChartExportSelection = { chart_id: chartId, chart_type: chartType,
    ...(taskId === undefined ? {} : { task_id: taskId }),
    ...(productIndex === undefined ? {} : { product_index: productIndex }) };
  async function download() {
    if (busy || !canExport) return;
    setBusy(true); setError('');
    try { await downloadResultExport(source, 'png', userId, selection); }
    catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="chart-export-action">
    <button type="button" disabled={busy || !canExport} aria-label={`下载${title} PNG`} onClick={() => void download()}>
      {busy ? '正在生成 PNG…' : '下载 PNG'}
    </button>
    {error && <p role="alert">{error}</p>}
  </div>;
}
