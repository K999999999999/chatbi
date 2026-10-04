import { useMemo } from 'react';
import { object } from './parse';
import { DataChart } from './Chart';
import { buildChartPlans } from './chartPlan';
import { decodeMetadata, type ResultMetadata } from './resultMetadata';
import { displayValue, roundedToZero } from './numberFormat';
export { object } from './parse';

export type Cell = string | number | boolean | null;
export type TableData = { columns: string[]; rows: Cell[][]; row_count: number; truncated: boolean; result_metadata?: ResultMetadata };
export type QuerySnapshot = TableData & { request_id: string; sql: string };
export type QueryResult = QuerySnapshot & { conversation_id: string };

export function text(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error('响应文字无效');
  return value;
}
export function strings(value: unknown): string[] {
  if (!Array.isArray(value) || !value.every(x => typeof x === 'string')) throw new Error('响应列表无效');
  return value;
}
export function tableData(value: unknown): TableData {
  const p = object(value);
  const columns = strings(p.columns);
  if (!Array.isArray(p.rows) || p.rows.length > 100 || !p.rows.every(row => Array.isArray(row)
      && row.length === columns.length && row.every(cell => cell === null || typeof cell === 'string'
        || typeof cell === 'boolean' || (typeof cell === 'number' && Number.isFinite(cell))))
      || !Number.isSafeInteger(p.row_count) || Number(p.row_count) < p.rows.length
      || typeof p.truncated !== 'boolean' || (Number(p.row_count) !== p.rows.length && !p.truncated)) throw new Error('响应表格无效');
  return { columns, rows: p.rows as Cell[][], row_count: Number(p.row_count), truncated: p.truncated,
    result_metadata: decodeMetadata(p.result_metadata, columns, p.rows.length) };
}
export function queryResult(value: unknown): QueryResult {
  return { ...querySnapshot(value), conversation_id: text(object(value).conversation_id) };
}
export function querySnapshot(value: unknown): QuerySnapshot {
  const p = object(value);
  if (p.row_count !== (p.rows as unknown[])?.length) throw new Error('响应行数无效');
  if (p.mode !== undefined && p.mode !== 'query') throw new Error('响应模式无效');
  return { ...tableData(p), request_id: text(p.request_id), sql: text(p.sql) };
}

export function ResultTable({ data }: { data: TableData }) {
  return <div className="result-table">
    <p className="result-meta">展示 {data.rows.length} 行{data.truncated ? ' · 结果已截断，仅展示部分数据（最多 100 行）。' : ''}</p>
    {!data.rows.length ? <p>查询成功，没有匹配的数据。</p> : <div className="table-scroll"><table>
      <thead><tr>{data.columns.map((name, i) => <th key={i}>{data.result_metadata?.columns[i]?.semantic_name ?? name}</th>)}</tr></thead>
      <tbody>{data.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>
        <span>{displayValue(cell, data.result_metadata?.columns[j])}</span>
        {roundedToZero(cell, data.result_metadata?.columns[j]) && <span className="missing">（显示值已舍入）</span>}
        {cell !== null && cell !== '' && displayValue(cell, data.result_metadata?.columns[j]) !== String(cell)
          && <details className="raw-value"><summary>查看原始值</summary><code>{String(cell)}</code></details>}
      </td>)}</tr>)}</tbody>
    </table></div>}
  </div>;
}

export function ResultExplanation({ data }: { data: TableData }) {
  const meta = data.result_metadata;
  if (!meta) return <p className="result-meta">结果说明未确认，保留原始表格。</p>;
  const scope = meta.scope;
  return <section className="result-explanation" aria-label="结果说明">
    {meta.columns.filter(c => c.role === 'metric').map(c => <p key={c.index}>
      <strong>{c.semantic_name}</strong> · {c.unit?.label ?? '单位未确认'}{c.definition && ' · ' + c.definition}</p>)}
    {scope.time_status === 'confirmed' && scope.time && <p>查询时间：{scope.time.start} 至 {scope.time.end_exclusive} 前 · {scope.time.time_basis}</p>}
    {scope.time_status === 'unbounded' && <p>查询时间：未限定时间范围。</p>}
    {scope.status !== 'complete' && <p>查询范围未完整确认。</p>}
    {scope.filters.map((f, i) => <p key={i}>{f.label} {f.operator} {f.values.join('、')}</p>)}
    {meta.columns.some(c => !c.certified) && <p>部分列含义或单位未确认，按原始值展示。</p>}
  </section>;
}

export function ResultView({ data }: { data: TableData }) {
  const meta = data.result_metadata;
  const charts = useMemo(() => buildChartPlans(data), [data]);
  const metrics = meta?.columns.filter(c => c.certified && c.role === 'metric') ?? [];
  const scalar = data.rows.length === 1 && meta && !meta.scope.grouping.length && !meta.scope.warnings.includes('GROUPING_UNCONFIRMED');
  return <section className="result-view"><ResultExplanation data={data}/>
    {scalar && metrics.length > 0 && <details open className="result-visual"><summary>指标卡</summary><div className="metric-grid">
      {metrics.map(c => <div key={c.index}><span>{c.semantic_name}</span>
        <strong>{displayValue(data.rows[0][c.index], c)}</strong>
        {roundedToZero(data.rows[0][c.index], c) && <span>显示值已舍入</span>}
        <details className="raw-value"><summary>查看原始值</summary><code>{String(data.rows[0][c.index] ?? '无数据')}</code></details>
      </div>)}
    </div></details>}
    {charts.plans.length > 0 && <details open className="result-visual"><summary>图表</summary>
      {charts.plans.map(plan => <DataChart key={plan.id} plan={plan}/>)}</details>}
    {charts.reason && <p className="result-meta">{charts.reason}</p>}
    <details open><summary>表格</summary><ResultTable data={data}/></details>
  </section>;
}
